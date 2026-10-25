"""Flask application for the optional Web UI."""

from __future__ import annotations

import secrets
import threading
import time
import webbrowser
from datetime import timedelta
from functools import wraps
from typing import Dict, Tuple
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .. import i18n
from ..pixi import PixiError
from ..state import AppState
from .auth import AuthStore
from .service import WebService, WebServiceError

APP_TITLE = "Pixi Environment Manager"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8010
PUBLIC_ENDPOINTS = {
    "login",
    "login_post",
    "static",
    "health",
    "favicon",
    "api_i18n",
}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class LoginLimiter:
    def __init__(self, attempts: int = 5, window_seconds: int = 300):
        self.attempts = attempts
        self.window = window_seconds
        self._items: Dict[str, list] = {}
        self._lock = threading.Lock()

    def allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            values = [
                stamp
                for stamp in self._items.get(key, [])
                if now - stamp < self.window
            ]
            self._items[key] = values
            return len(values) < self.attempts

    def fail(self, key: str) -> None:
        with self._lock:
            self._items.setdefault(key, []).append(time.time())

    def clear(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)


def create_app(
    service: WebService,
    auth: AuthStore,
    *,
    host: str = DEFAULT_HOST,
) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.config.update(
        SECRET_KEY=auth.secret_key,
        SESSION_COOKIE_NAME="pixi_env_manager_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        PERMANENT_SESSION_LIFETIME=timedelta(days=auth.session_days),
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    )
    limiter = LoginLimiter()

    def _render_login(error: str = "", status: int = 200):
        preferences = service.settings()
        language = preferences["language"]
        return (
            render_template(
                "login.html",
                app_title=APP_TITLE,
                csrf=_csrf(),
                error=error,
                language=language,
                theme=preferences["theme"],
                languages=i18n.LANGUAGES,
                t=lambda text: i18n.translate_for(text, language),
            ),
            status,
        )

    def _csrf() -> str:
        token = str(session.get("csrf") or "")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf"] = token
        return token

    def _is_api() -> bool:
        return request.path.startswith("/api/")

    def _api_error(message: str, status: int = 400) -> Tuple[Response, int]:
        return jsonify({"error": message}), status

    def _login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("authenticated"):
                if _is_api():
                    return _api_error("Not authenticated.", 401)
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def _guard():
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if request.endpoint == "login":
            return None
        if not session.get("authenticated"):
            if _is_api():
                return _api_error("Not authenticated.", 401)
            return redirect(url_for("login", next=request.path))
        if request.method in MUTATING_METHODS:
            token = request.headers.get("X-CSRF-Token", "")
            if request.endpoint == "logout" and not token:
                token = request.form.get("csrf", "")
            if not token or token != session.get("csrf"):
                return _api_error("Invalid CSRF token.", 403)
            origin = request.headers.get("Origin")
            if origin:
                parsed = urlparse(origin)
                if parsed.netloc and parsed.netloc != request.host:
                    return _api_error("Invalid origin.", 403)
        return None

    @app.after_request
    def _headers(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(WebServiceError)
    def _service_error(exc: WebServiceError):
        return _api_error(exc.message, exc.status)

    @app.errorhandler(PixiError)
    def _pixi_error(exc: PixiError):
        return _api_error(str(exc), 500)

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "app": APP_TITLE})

    @app.get("/favicon.ico")
    def favicon():
        return Response(status=204)

    @app.get("/login")
    def login():
        if session.get("authenticated"):
            return redirect(url_for("index"))
        return _render_login()

    @app.post("/login")
    def login_post():
        if not limiter.allowed(request.remote_addr or "unknown"):
            language = service.settings()["language"]
            return _render_login(
                i18n.translate_for(
                    "Too many attempts. Try again later.", language
                ),
                429,
            )
        token = request.form.get("csrf", "")
        if not token or token != session.get("csrf"):
            return redirect(url_for("login"))
        password = request.form.get("password", "")
        if not password or not auth.verify(password):
            limiter.fail(request.remote_addr or "unknown")
            language = service.settings()["language"]
            return _render_login(
                i18n.translate_for("Incorrect password.", language),
                401,
            )
        limiter.clear(request.remote_addr or "unknown")
        session.clear()
        session["authenticated"] = True
        session["csrf"] = secrets.token_urlsafe(32)
        session.permanent = True
        target = request.args.get("next") or url_for("index")
        parsed_target = urlparse(str(target))
        if parsed_target.scheme or parsed_target.netloc or not str(target).startswith("/"):
            target = url_for("index")
        return redirect(target)

    @app.post("/logout")
    @_login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @_login_required
    def index():
        preferences = service.settings()
        return render_template(
            "index.html",
            app_title=APP_TITLE,
            csrf=_csrf(),
            language=preferences["language"],
            theme=preferences["theme"],
            languages=i18n.LANGUAGES,
        )

    @app.get("/api/i18n/<language>")
    def api_i18n(language: str):
        language = language if language in i18n.LANGUAGES else "en"
        return jsonify(
            {
                "language": language,
                "languages": i18n.LANGUAGES,
                "messages": i18n.catalog_for(language),
            }
        )

    @app.get("/api/session")
    @_login_required
    def api_session():
        preferences = service.settings()
        return jsonify(
            {
                "authenticated": True,
                "csrf": _csrf(),
                "language": preferences["language"],
                "theme": preferences["theme"],
                "languages": i18n.LANGUAGES,
                "title": APP_TITLE,
                "host": host,
            }
        )

    @app.get("/api/workspace")
    @_login_required
    def api_workspace():
        return jsonify(service.summary())

    @app.post("/api/workspace/auto-open")
    @_login_required
    def api_auto_open_workspace():
        return jsonify(service.auto_open_recent())

    @app.post("/api/workspace/open")
    @_login_required
    def api_open_workspace():
        payload = request.get_json(silent=True) or {}
        return jsonify(
            service.open_workspace(
                str(payload.get("path") or ""),
                str(payload.get("environment") or ""),
            )
        )

    @app.post("/api/workspace/refresh")
    @_login_required
    def api_refresh_workspace():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.refresh(str(payload.get("environment") or "")))

    @app.post("/api/environment")
    @_login_required
    def api_environment():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.set_environment(str(payload.get("environment") or "")))

    @app.get("/api/packages")
    @_login_required
    def api_packages():
        summary = service.summary()
        return jsonify(
            {
                "packages": summary.get("packages", []),
                "environment": summary.get("environment"),
                "base_mode": summary.get("base_mode"),
            }
        )

    @app.post("/api/packages/latest")
    @_login_required
    def api_latest():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.query_latest(str(payload.get("name") or "")))

    @app.post("/api/packages/compatible")
    @_login_required
    def api_compatible():
        return jsonify(service.compatible_updates())

    @app.get("/api/environments/features")
    @_login_required
    def api_features():
        return jsonify({"features": service.feature_names()})

    @app.post("/api/jobs")
    @_login_required
    def api_jobs():
        payload = request.get_json(silent=True) or {}
        kind = str(payload.get("kind") or "")
        if kind == "add_environment":
            return jsonify(
                service.add_environment(
                    str(payload.get("name") or ""),
                    [str(item) for item in payload.get("features") or []],
                    str(payload.get("solve_group") or ""),
                    bool(payload.get("use_default", True)),
                    bool(payload.get("install", True)),
                )
            )
        if kind == "remove_environment":
            return jsonify(
                service.remove_environment(
                    str(payload.get("name") or ""),
                    bool(payload.get("cleanup")),
                )
            )
        if kind == "task":
            return jsonify(
                service.run_task(
                    str(payload.get("name") or ""),
                    str(payload.get("args") or ""),
                    bool(payload.get("terminal")),
                )
            )
        if kind == "python":
            return jsonify(
                service.run_python(
                    str(payload.get("script") or ""),
                    str(payload.get("args") or ""),
                    str(payload.get("cwd") or ""),
                    bool(payload.get("terminal")),
                )
            )
        if kind == "command":
            return jsonify(
                service.run_command(
                    str(payload.get("command") or ""),
                    bool(payload.get("terminal")),
                )
            )
        if kind == "add":
            return jsonify(
                service.add_package(
                    [str(item) for item in payload.get("specs") or []],
                    pypi=bool(payload.get("pypi")),
                    environment=str(payload.get("environment") or ""),
                    feature=str(payload.get("feature") or ""),
                    no_install=bool(payload.get("no_install")),
                )
            )
        if kind == "remove":
            return jsonify(
                service.remove_package(
                    [str(item) for item in payload.get("specs") or []],
                    pypi=bool(payload.get("pypi")),
                    environment=str(payload.get("environment") or ""),
                    feature=str(payload.get("feature") or ""),
                )
            )
        if kind == "install":
            return jsonify(service.install())
        if kind == "update":
            return jsonify(
                service.update_package(
                    str(payload.get("name") or ""),
                    bool(payload.get("upgrade")),
                )
            )
        if kind == "create_workspace":
            return jsonify(
                service.create_workspace(
                    str(payload.get("path") or ""),
                    [str(item) for item in payload.get("channels") or []],
                    [str(item) for item in payload.get("platforms") or []],
                )
            )
        raise WebServiceError("Unknown job kind.")

    @app.get("/api/jobs/<int:job_id>")
    @_login_required
    def api_job(job_id: int):
        offset = request.args.get("offset", "0")
        try:
            offset_int = int(offset)
        except ValueError:
            offset_int = 0
        return jsonify(service.job_status(job_id, offset_int))

    @app.post("/api/jobs/<int:job_id>/stop")
    @_login_required
    def api_stop_job(job_id: int):
        return jsonify(service.stop_job(job_id))

    @app.post("/api/jobs/stop_all")
    @_login_required
    def api_stop_all_jobs():
        return jsonify(service.stop_all_jobs())

    @app.get("/api/settings")
    @_login_required
    def api_settings():
        return jsonify(service.settings())

    @app.post("/api/settings")
    @_login_required
    def api_update_settings():
        payload = request.get_json(silent=True) or {}
        terminal = payload.get("terminal")
        language = payload.get("language")
        theme = payload.get("theme")
        return jsonify(
            service.update_settings(
                terminal=str(terminal) if terminal is not None else None,
                language=str(language) if language is not None else None,
                theme=str(theme) if theme is not None else None,
            )
        )

    @app.get("/api/editor")
    @_login_required
    def api_editor_read():
        return jsonify(service.read_manifest())

    @app.put("/api/editor")
    @_login_required
    def api_editor_write():
        payload = request.get_json(silent=True) or {}
        return jsonify(service.write_manifest(str(payload.get("content") or "")))

    return app


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> int:
    auth = AuthStore()
    if not auth.configured:
        print("Web password is not configured.", flush=True)
        print("Run: start.bat --web --set-password", flush=True)
        return 1
    state = AppState()
    service = WebService(state)
    app = create_app(service, auth, host=host)
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = "http://{}:{}".format(browser_host, port)
    print("{} Web UI: {}".format(APP_TITLE, url), flush=True)
    if host in ("0.0.0.0", "::"):
        print("WARNING: Web UI is exposed to the local network.", flush=True)
        print("WARNING: HTTP is unencrypted; use only on a trusted LAN.", flush=True)
        print("Open http://<this-computer-ip>:{} from another computer.".format(port), flush=True)
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
    return 0
