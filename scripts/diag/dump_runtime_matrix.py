#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[2]

SERVICE_FILES = {
    "integration-hub": ROOT / "platform/integration-hub/neft_integration_hub/settings.py",
    "document-service": ROOT / "platform/document-service/app/settings.py",
    "logistics-service": ROOT / "platform/logistics-service/neft_logistics_service/settings.py",
    "processing-core": ROOT / "shared/python/neft_shared/settings.py",
}

WATCH_KEYS = {
    "APP_ENV",
    "PROVIDER_X_MODE",
    "DIADOK_MODE",
    "NOTIFICATIONS_MODE",
    "EMAIL_PROVIDER_MODE",
    "OTP_PROVIDER_MODE",
    "LOGISTICS_PROVIDER",
    "LOGISTICS_COMPUTE_PROVIDER",
    "USE_MOCK_LOGISTICS",
    "SMS_PROVIDER",
    "VOICE_PROVIDER",
    "USE_STUB_EDO",
    "USE_STUB_CRM",
    "ALLOW_MOCK_PROVIDERS_IN_PROD",
}

ALLOWED_VALUES = {
    "APP_ENV": ["dev", "test", "prod", "production"],
    "PROVIDER_X_MODE": ["mock", "stub", "real", "prod", "production", "sandbox", "degraded", "disabled"],
    "DIADOK_MODE": ["mock", "stub", "real", "prod", "production", "sandbox", "degraded", "disabled"],
    "NOTIFICATIONS_MODE": ["mock", "real", "prod", "production", "sandbox", "degraded", "disabled"],
    "EMAIL_PROVIDER_MODE": ["mock", "smtp", "disabled", "degraded"],
    "OTP_PROVIDER_MODE": ["mock", "real", "prod", "production", "sandbox", "degraded", "disabled"],
    "LOGISTICS_PROVIDER": ["mock", "stub", "integration_hub", "degraded", "disabled"],
    "LOGISTICS_COMPUTE_PROVIDER": ["mock", "stub", "osrm", "degraded", "disabled"],
    "USE_MOCK_LOGISTICS": ["0", "1"],
    "USE_STUB_EDO": ["0", "1"],
    "USE_STUB_CRM": ["0", "1"],
    "SMS_PROVIDER": ["disabled", "degraded", "stub", "sms_stub"],
    "VOICE_PROVIDER": ["disabled", "degraded", "stub", "voice_stub"],
    "ALLOW_MOCK_PROVIDERS_IN_PROD": ["0", "1"],
}

DERIVED_DEFAULTS = {
    ("logistics-service", "LOGISTICS_PROVIDER"): "integration_hub",
    ("logistics-service", "LOGISTICS_COMPUTE_PROVIDER"): "osrm",
}

RISK_TERMS = ("mock", "stub", "placeholder")


@dataclass
class SettingFact:
    service: str
    key: str
    default: str
    where: str


def _write_utf8_lf(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant):
        return str(node.value)
    return None


def parse_settings_py(service: str, path: Path) -> list[SettingFact]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[SettingFact] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "getenv":
                if not node.args:
                    continue
                key = literal(node.args[0])
                if not key or key not in WATCH_KEYS:
                    continue
                default = "UNKNOWN"
                if len(node.args) > 1:
                    d = literal(node.args[1])
                    if d is not None:
                        default = d
                src = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                found.append(SettingFact(service, key, default, f"{path.relative_to(ROOT)}:{node.lineno} `{src}`"))
    uniq: dict[tuple[str, str], SettingFact] = {}
    for fact in found:
        uniq.setdefault((fact.service, fact.key), fact)
    return list(uniq.values())


def parse_env_file(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.exists():
        return vals
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        vals[k.strip()] = v.strip()
    return vals


def parse_compose() -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    for compose_name in ("docker-compose.yml", "docker-compose.dev.yml", "docker-compose.test.yml"):
        compose_path = ROOT / compose_name
        if not compose_path.exists() or yaml is None:
            continue
        data = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        services = data.get("services", {})
        for svc, payload in services.items():
            env = payload.get("environment", {}) or {}
            svc_map = results.setdefault(svc, {})
            if isinstance(env, list):
                for item in env:
                    if isinstance(item, str) and "=" in item:
                        k, v = item.split("=", 1)
                        svc_map[k] = v
            elif isinstance(env, dict):
                for k, v in env.items():
                    svc_map[str(k)] = "" if v is None else str(v)
    return results


def classify_risk(default: str) -> str:
    d = (default or "").lower()
    if d == "unknown":
        return "UNKNOWN"
    if any(term in d for term in RISK_TERMS):
        return "RISK"
    return "SAFE"


def main() -> None:
    compose_env = parse_compose()
    env_example = parse_env_file(ROOT / ".env.example")
    rows: list[dict[str, Any]] = []

    service_compose_alias = {
        "integration-hub": "integration-hub",
        "document-service": "document-service",
        "logistics-service": "logistics-service",
        "processing-core": "core-api",
    }

    for service, path in SERVICE_FILES.items():
        for fact in parse_settings_py(service, path):
            compose_service = service_compose_alias.get(service, service)
            compose_value = compose_env.get(compose_service, {}).get(fact.key)
            overridden = compose_value is not None
            derived_default = DERIVED_DEFAULTS.get((fact.service, fact.key))
            if fact.default == "UNKNOWN" and derived_default is not None:
                fact.default = derived_default
            if fact.default == "UNKNOWN" and fact.key in env_example:
                fact.default = env_example[fact.key]
            risk_value = compose_value if overridden else fact.default
            rows.append(
                {
                    "service": service,
                    "setting_key": fact.key,
                    "default": fact.default,
                    "allowed_values": ALLOWED_VALUES.get(fact.key, []),
                    "where_defined": fact.where,
                    "overridden_in_compose": overridden,
                    "compose_value": compose_value,
                    "risk": classify_risk(risk_value or fact.default),
                }
            )

    rows.sort(key=lambda r: (r["service"], r["setting_key"]))
    out_dir = ROOT / "docs/diag/runtime_matrix"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "runtime_matrix.json"
    _write_utf8_lf(out_json, json.dumps(rows, ensure_ascii=False, indent=2))

    doc = ROOT / "docs/diag/PR8_DEFAULT_RUNTIME_MATRIX.md"
    header = "| Service | Setting key | Default | Allowed values | Where defined | Overridden in compose? | Compose value | Risk |\n"
    sep = "|---|---|---|---|---|---|---|---|\n"
    lines = [
        "# PR-8 Default Runtime Matrix\n",
        "Generated by `python scripts/diag/dump_runtime_matrix.py`.\n",
        "\n",
        "Risk criteria:\n",
        "- `SAFE` means the default is real/prod/non-mock.\n",
        "- `RISK` means the default contains mock/stub/placeholder.\n",
        "- `UNKNOWN` means the default could not be extracted statically.\n\n",
        header,
        sep,
    ]
    for r in rows:
        allowed = ", ".join(r["allowed_values"]) if r["allowed_values"] else ""
        lines.append(
            f"| {r['service']} | {r['setting_key']} | {r['default']} | {allowed} | {r['where_defined']} | {str(r['overridden_in_compose']).lower()} | {r['compose_value'] or ''} | {r['risk']} |\n"
        )
    _write_utf8_lf(doc, "".join(lines))
    print(f"wrote {out_json.relative_to(ROOT)} and {doc.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
