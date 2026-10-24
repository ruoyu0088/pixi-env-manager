"""Read dependency scopes from a Pixi manifest.

Pixi has three relevant dependency scopes:

* the default feature (``[dependencies]`` / ``[pypi-dependencies]``), shared by
  every environment unless default-feature inheritance is disabled;
* named features (``[feature.<name>.dependencies]``);
* environment-only dependencies (``[environments.<name>.dependencies]``).

This module never writes the manifest; the GUI uses the information for display
and for choosing the correct add/remove target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import tomllib
except ImportError:  # pragma: no cover - fallback for Python < 3.11
    tomllib = None  # type: ignore[assignment]


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


@dataclass
class DependencySpec:
    name: str
    spec: str = ""
    kind: str = "conda"


@dataclass
class ManifestScopes:
    base: Dict[str, DependencySpec] = field(default_factory=dict)
    features: Dict[str, Dict[str, DependencySpec]] = field(default_factory=dict)
    environments: Dict[str, Dict[str, DependencySpec]] = field(default_factory=dict)

    def scope_for(self, package_name: str) -> str:
        normalized = normalize_package_name(package_name)
        if normalized in self.base:
            return "base"
        for feature, dependencies in self.features.items():
            if normalized in dependencies:
                return "feature:" + feature
        for environment, dependencies in self.environments.items():
            if normalized in dependencies:
                return "env:" + environment
        return "transitive"

    def base_packages(self) -> List[DependencySpec]:
        return list(self.base.values())

    def all_explicit_names(self) -> set:
        names = set(self.base)
        for dependencies in self.features.values():
            names.update(dependencies)
        for dependencies in self.environments.values():
            names.update(dependencies)
        return names


def _dependencies(table: dict) -> Dict[str, DependencySpec]:
    result: Dict[str, DependencySpec] = {}
    for section, kind in (
        ("dependencies", "conda"),
        ("pypi-dependencies", "pypi"),
    ):
        value = table.get(section)
        if not isinstance(value, dict):
            continue
        for name, spec in value.items():
            if not isinstance(name, str):
                continue
            result[normalize_package_name(name)] = DependencySpec(
                name=name,
                spec=str(spec),
                kind=kind,
            )
    return result


def _from_mapping(data: dict) -> ManifestScopes:
    scopes = ManifestScopes()
    scopes.base = _dependencies(data)
    features = data.get("feature")
    if isinstance(features, dict):
        for name, table in features.items():
            if isinstance(table, dict):
                scopes.features[str(name)] = _dependencies(table)
    environments = data.get("environments")
    if isinstance(environments, dict):
        for name, value in environments.items():
            if isinstance(value, dict):
                scopes.environments[str(name)] = _dependencies(value)
    return scopes


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
_KEY_RE = re.compile(r"^\s*([A-Za-z0-9_.\-\"']+)\s*=\s*(.*?)\s*(?:#.*)?$")


def _fallback_parse(text: str) -> ManifestScopes:
    """Best-effort parser for Python 3.9/3.10 (no tomllib)."""

    scopes = ManifestScopes()
    section = ""
    for line in text.splitlines():
        match = _SECTION_RE.match(line)
        if match:
            section = match.group(1).strip()
            continue
        if not section or section.startswith("workspace"):
            continue
        key_match = _KEY_RE.match(line)
        if not key_match:
            continue
        name = key_match.group(1).strip().strip("\"'")
        spec = key_match.group(2).strip().strip("\"'")
        parts = section.split(".")
        kind = "pypi" if "pypi-dependencies" in parts else "conda"
        if section in ("dependencies", "pypi-dependencies"):
            target = scopes.base
        elif len(parts) >= 3 and parts[0] == "feature" and parts[-1] in (
            "dependencies",
            "pypi-dependencies",
        ):
            target = scopes.features.setdefault(parts[1], {})
        elif len(parts) >= 3 and parts[0] == "environments" and parts[-1] in (
            "dependencies",
            "pypi-dependencies",
        ):
            target = scopes.environments.setdefault(parts[1], {})
        elif len(parts) >= 4 and parts[:2] == ["tool", "pixi"]:
            rest = parts[2:]
            if rest in (["dependencies"], ["pypi-dependencies"]):
                target = scopes.base
            elif len(rest) >= 3 and rest[0] == "feature" and rest[-1] in (
                "dependencies",
                "pypi-dependencies",
            ):
                target = scopes.features.setdefault(rest[1], {})
            elif len(rest) >= 3 and rest[0] == "environments" and rest[-1] in (
                "dependencies",
                "pypi-dependencies",
            ):
                target = scopes.environments.setdefault(rest[1], {})
            else:
                continue
        else:
            continue
        target[normalize_package_name(name)] = DependencySpec(
            name=name, spec=spec, kind=kind
        )
    return scopes


def read_manifest_scopes(manifest: Path) -> ManifestScopes:
    try:
        raw = manifest.read_bytes()
        text = raw.decode("utf-8-sig")
    except OSError:
        return ManifestScopes()
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception:
            return _fallback_parse(text)
        if manifest.name == "pyproject.toml":
            data = (data.get("tool") or {}).get("pixi") or {}
        if isinstance(data, dict):
            return _from_mapping(data)
    return _fallback_parse(text)
