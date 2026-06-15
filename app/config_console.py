from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, DATA_DIR, PROJECT_ROOT

ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
CONFIG_BACKUP_DIR = DATA_DIR / "config_backups"
CONFIG_AUDIT_DIR = DATA_DIR / "config_audit"
CONFIG_CONFIRMATION_PHRASE = "I_UNDERSTAND_CONFIG_CAN_CHANGE_SAFETY_POSTURE"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ConfigOption:
    key: str
    label: str
    description: str
    help_text: str
    group: str
    value_type: str
    control: str
    default_value: str = ""
    allowed_values: list[str] = field(default_factory=list)
    recommended_values: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    restart_required: bool = True
    secret: bool = False
    advanced: bool = False
    dangerous: bool = False
    affects_live_trading: bool = False
    affects_training_jobs: bool = False
    affects_lan_exposure: bool = False
    validation_rules: list[str] = field(default_factory=list)
    warning_messages: list[str] = field(default_factory=list)
    blocker_messages: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_text(value: Any) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _parse_env_lines(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Parse a simple .env-style file while preserving raw lines for rewrite."""
    rows: list[dict[str, Any]] = []
    values: dict[str, str] = {}
    text = _read_text(path)
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
        if match and not line.lstrip().startswith("#"):
            key = match.group(1)
            value = match.group(2)
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            rows.append({"type": "assignment", "key": key, "raw": line})
            values[key] = value
        else:
            rows.append({"type": "raw", "raw": line})
    return rows, values


def _example_values() -> dict[str, str]:
    _, values = _parse_env_lines(ENV_EXAMPLE_PATH)
    return values


def _dot_env_values() -> dict[str, str]:
    _, values = _parse_env_lines(ENV_PATH)
    return values


def _source_for(key: str, dotenv_values: dict[str, str], defaults: dict[str, str]) -> str:
    if key in dotenv_values and os.environ.get(key, dotenv_values[key]) == dotenv_values[key]:
        return ".env"
    if key in os.environ:
        return "process_environment"
    if key in dotenv_values:
        return ".env"
    if key in defaults:
        return ".env.example_default"
    return "unset"


def _effective_value(key: str, dotenv_values: dict[str, str], defaults: dict[str, str]) -> str:
    if key in os.environ:
        return os.environ.get(key, "")
    if key in dotenv_values:
        return dotenv_values.get(key, "")
    return defaults.get(key, "")


def _label_for_key(key: str) -> str:
    words = key.replace("POLYMARKET_", "").replace("POLY_", "").replace("CLOB_", "CLOB ").replace("_", " ")
    words = re.sub(r"\s+", " ", words).strip().title()
    return words.replace("Api", "API").replace("Url", "URL").replace("Clob", "CLOB").replace("Id", "ID")


def _group_for_key(key: str) -> str:
    if key in {"HOST", "PORT", "APP_RELOAD", "ALLOWED_HOSTS", "SECURITY_HEADERS_ENABLED", "SESSION_COOKIE_SECURE", "SESSION_COOKIE_SAMESITE"}:
        return "Server and LAN access"
    if key in {"APP_MODE", "READ_ONLY", "DEFAULT_LIMIT", "REQUEST_TIMEOUT_SECONDS", "SOURCE_CHECK_TIMEOUT"}:
        return "First-run setup"
    if key in {"OPENAI_API_KEY", "NEWS_API_KEY"}:
        return "Optional integrations"
    if key.startswith("PAPER_"):
        return "Paper trading"
    if key.startswith("TRAINING_"):
        return "Training Lab"
    if key.startswith("POLYMARKET_TRAINING_"):
        if key in {"POLYMARKET_TRAINING_MAX_ROWS", "POLYMARKET_TRAINING_DEFAULT_MAX_ROWS", "POLYMARKET_TRAINING_HARD_MAX_ROWS", "POLYMARKET_TRAINING_BATCH_SIZE", "POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS", "POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS", "POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES"}:
            return "100K batch training"
        return "Host training jobs"
    if key.startswith("POLYMARKET_DATA_ALLOWED") or key.startswith("POLYMARKET_DATA_ALLOW_INTERNET") or key.startswith("POLYMARKET_DATA_USER_AGENT") or key.startswith("POLYMARKET_DATA_REQUEST") or key.startswith("POLYMARKET_DATA_RATE") or key.startswith("POLYMARKET_DATA_MAX_RAW") or key.startswith("POLYMARKET_DATA_STORE") or key.startswith("POLYMARKET_DATA_REQUIRE") or key.startswith("POLYMARKET_DATA_MAX_REQUESTS"):
        return "Internet ingestion"
    if key.startswith("POLYMARKET_DATA_MAX_BACKFILL") or key.startswith("POLYMARKET_DATA_BACKFILL") or key.startswith("POLYMARKET_DATA_MAX_STORAGE") or key.startswith("POLYMARKET_DATA_BLOCK_LARGE"):
        return "Category datasets"
    if key.startswith("POLYMARKET_DATA_"):
        return "Dataset builder"
    if key in {"GAMMA_BASE_URL", "CLOB_BASE_URL", "POLYMARKET_CLOB_HOST"}:
        return "Data source registry"
    if key.startswith("LIVE_"):
        return "Live-trading readiness"
    if key.startswith("POLYMARKET_MARKET_DATA_"):
        return "Market data intelligence"
    if key.startswith("POLYMARKET_AUTONOMOUS_"):
        return "Manual review queues"
    if key.startswith("POLYMARKET_LIVE_SDK_") or key.startswith("POLYMARKET_LIVE_READONLY_REQUEST") or key.startswith("POLYMARKET_LIVE_SUBMIT_SMOKE") or key.startswith("POLYMARKET_LIVE_CANCEL_SMOKE"):
        return "Live adapter SDK mapping"
    if key.startswith("POLYMARKET_LIVE_"):
        if any(token in key for token in ["MAX_", "ALLOWLIST"]):
            return "Risk controls"
        if any(token in key for token in ["SUBMIT", "CANCEL", "MANUAL", "AUTHORIZATION", "DRY_RUN", "ADAPTER_REQUEST", "FINAL_CONFIRMATION", "EMERGENCY"]):
            return "Live execution gates"
        return "Live-trading readiness"
    if key.startswith("POLYMARKET_") or key.startswith("POLY_") or key.startswith("CLOB_"):
        return "Authentication and admin setup"
    return "Advanced/debug settings"


def _is_secret_key(key: str) -> bool:
    if "ALLOWLIST" in key or "ALLOWED" in key:
        return False
    return any(token in key for token in ["PRIVATE_KEY", "API_KEY", "SECRET", "PASSPHRASE"])


def _is_live_key(key: str) -> bool:
    return key.startswith("LIVE_") or key.startswith("POLYMARKET_LIVE_") or key.startswith("POLYMARKET_AUTONOMOUS_") or key in {
        "LIVE_TRADING_ENABLED", "POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", "POLY_API_KEY", "POLYMARKET_CLOB_API_KEY", "CLOB_API_KEY", "POLY_SECRET", "POLYMARKET_CLOB_SECRET", "CLOB_SECRET", "POLY_PASSPHRASE", "POLYMARKET_CLOB_PASSPHRASE", "CLOB_PASSPHRASE",
    }


def _is_dangerous_key(key: str) -> bool:
    dangerous_tokens = [
        "LIVE_TRADING_ENABLED", "LIVE_ENABLE_SUBMIT", "LIVE_ENABLE_CANCEL", "LIVE_ENABLE_AUTONOMOUS", "LIVE_ALLOW_REAL_NETWORK", "LIVE_MANUAL_SUBMIT_ENABLED", "LIVE_MANUAL_CANCEL_ENABLED", "LIVE_REAL_ADAPTER_EXPERIMENTAL", "RUN_REAL_LIVE_TESTS", "EMERGENCY_CANCEL_ENABLED", "AUTONOMOUS_SCHEDULER_ENABLED",
    ]
    return any(token in key for token in dangerous_tokens)


def _is_advanced_key(key: str) -> bool:
    return _is_live_key(key) or key.startswith("POLYMARKET_MARKET_DATA_") or "SDK" in key or key.endswith("CONFIRMATION") or key.endswith("PHRASE") or key.startswith("POLYMARKET_AUTONOMOUS_")


def _looks_bool(default: str, key: str) -> bool:
    if str(default).strip().lower() in TRUE_VALUES | FALSE_VALUES:
        return True
    suffixes = ("_ENABLED", "_REQUIRED", "_ONLY", "_READONLY", "_SECURE", "_MODE", "_FETCH_ENABLED", "_ALLOW_NETWORK", "_ALLOW_INTERNET")
    if key.endswith(suffixes) and key not in {"APP_MODE", "POLYMARKET_LIVE_SDK_SUBMIT_METHOD", "POLYMARKET_LIVE_SDK_CANCEL_METHOD"}:
        return True
    return False


def _looks_int(default: str, key: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", str(default or ""))) and key not in {"POLYMARKET_CHAIN_ID"}


def _looks_float(default: str) -> bool:
    return bool(re.fullmatch(r"-?\d+\.\d+", str(default or "")))


def _allowed_values_for(key: str) -> list[str]:
    mapping = {
        "APP_MODE": ["read_only", "paper", "local_research"],
        "SESSION_COOKIE_SAMESITE": ["lax", "strict", "none"],
        "HOST": ["127.0.0.1", "0.0.0.0"],
        "POLYMARKET_CHAIN_ID": ["137"],
        "TRAINING_DEFAULT_MODEL_TYPE": ["heuristic_baseline", "threshold", "momentum", "walk_forward"],
        "POLYMARKET_DATA_DEFAULT_SPLIT_METHOD": ["chronological", "random", "walk_forward"],
        "POLYMARKET_LIVE_SDK_FAMILY": ["current_py_clob_client", "manual_review_only", "unconfigured"],
        "POLYMARKET_LIVE_SDK_SUBMIT_METHOD": ["create_order+post_order", "post_order", "disabled"],
        "POLYMARKET_LIVE_SDK_CANCEL_METHOD": ["cancel", "disabled"],
        "POLYMARKET_TRAINING_ALLOWED_JOB_TYPES": ["baseline_training", "threshold_training", "momentum_training", "walk_forward_backtest", "dataset_quality_scan", "feature_build", "signal_generation_preview"],
        "POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST": ["manual", "baseline", "threshold", "momentum", "walk_forward"],
    }
    return mapping.get(key, [])


def _describe_key(key: str, group: str) -> tuple[str, str]:
    base = {
        "POLYMARKET_TRAINING_HOST_JOBS_ENABLED": ("Enables the local host training job runner.", "This only permits local training/backtesting/signal-preview jobs; it does not permit live trading."),
        "POLYMARKET_TRAINING_MAX_ROWS": ("Maximum rows a host training job may select by default.", "Use with hard caps and batch size to support safe 100K local training runs."),
        "POLYMARKET_TRAINING_HARD_MAX_ROWS": ("Absolute upper bound for local host training jobs.", "Requests above this limit are blocked when block-over-hard-max is enabled."),
        "POLYMARKET_TRAINING_BATCH_SIZE": ("Number of rows processed per local training batch.", "Smaller batches use less memory; 5,000 is a reasonable 100K-run default on many 16 GB systems."),
        "LIVE_TRADING_ENABLED": ("Top-level live-trading readiness flag.", "Changing this does not bypass other live gates; real execution remains guarded."),
        "POLYMARKET_LIVE_ALLOW_REAL_NETWORK": ("Allows the live adapter to use real network paths when all other gates pass.", "Dangerous: keep disabled unless performing a deliberate live-readiness review."),
        "POLYMARKET_LIVE_ENABLE_SUBMIT": ("Enables the real submit gate when all other manual gates pass.", "Dangerous: this does not submit on its own but is execution-facing."),
        "POLYMARKET_LIVE_ENABLE_CANCEL": ("Enables the real cancel gate when all other manual gates pass.", "Dangerous: this does not cancel on its own but is execution-facing."),
        "HOST": ("Network interface the local web server binds to.", "Use 127.0.0.1 for local-only. Use 0.0.0.0 only when you intend LAN access."),
        "ALLOWED_HOSTS": ("Comma-separated HTTP Host allowlist.", "Use * only for local/LAN demo convenience; fixed hostnames/IPs are safer."),
    }
    if key in base:
        return base[key]
    if _is_secret_key(key):
        return (f"Secret credential/config value for {group.lower()}.", "Secrets are masked in the UI, audit logs, and sanitized exports.")
    if _is_live_key(key):
        return (f"Live-readiness or execution-boundary setting for {group.lower()}.", "Changing live-related values never bypasses backend gates, manual review, or kill-switch checks.")
    if "TRAINING" in key:
        return (f"Training configuration for {group.lower()}.", "Training outputs and signal previews remain manual-review-only and can_live_trade=false.")
    if "DATA" in key:
        return (f"Data configuration for {group.lower()}.", "Data and internet ingestion are operator-controlled and default to local-first safe behavior.")
    if key.startswith("PAPER_"):
        return (f"Paper-trading simulation control for {group.lower()}.", "Paper workflow values affect local simulations only.")
    return (f"Application configuration value for {group.lower()}.", "Use the guided control and validation rather than editing raw .env text when possible.")


def build_config_schema() -> list[ConfigOption]:
    defaults = _example_values()
    keys = list(defaults)
    # Add common app-managed paths even if absent from .env.example.
    for key, default in {
        "SNAPSHOT_DIR": str(DATA_DIR / "snapshots"),
        "LATEST_PATH": str(DATA_DIR / "latest_markets.json"),
    }.items():
        if key not in defaults:
            defaults[key] = default
            keys.append(key)

    seen: set[str] = set()
    schema: list[ConfigOption] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        default = str(defaults.get(key, ""))
        group = _group_for_key(key)
        allowed = _allowed_values_for(key)
        secret = _is_secret_key(key)
        affects_live = _is_live_key(key)
        affects_training = "TRAINING" in key or key.startswith("POLYMARKET_DATA_")
        affects_lan = key in {"HOST", "PORT", "ALLOWED_HOSTS", "SECURITY_HEADERS_ENABLED", "SESSION_COOKIE_SECURE", "SESSION_COOKIE_SAMESITE"}
        dangerous = _is_dangerous_key(key)
        advanced = _is_advanced_key(key) or key in {"SNAPSHOT_DIR", "LATEST_PATH"}
        description, help_text = _describe_key(key, group)
        warnings: list[str] = []
        blockers: list[str] = []
        rules: list[str] = []
        min_value: float | None = None
        max_value: float | None = None
        step: float | None = None
        value_type = "text"
        control = "text"

        if secret:
            value_type = "secret"
            control = "masked_secret"
            rules.append("Secret values are masked in UI, logs, audits, and exports.")
        elif allowed and key in {"POLYMARKET_TRAINING_ALLOWED_JOB_TYPES", "POLYMARKET_AUTONOMOUS_STRATEGY_ALLOWLIST"}:
            value_type = "multiselect"
            control = "multi_select"
            rules.append("Stored as a comma-separated allowlist after validation.")
        elif _looks_bool(default, key):
            value_type = "boolean"
            control = "toggle"
            allowed = ["true", "false"]
            rules.append("Must be true or false.")
        elif allowed:
            value_type = "enum"
            control = "radio" if len(allowed) <= 4 else "select"
            rules.append("Must be one of the allowed values.")
        elif key.endswith("_URL") or key.endswith("_HOST") or "BASE_URL" in key:
            value_type = "url"
            control = "text"
            rules.append("Must be a URL-like value when set.")
        elif key.endswith("_DIR") or key.endswith("_PATH"):
            value_type = "path"
            control = "path_text"
            rules.append("Filesystem path stored as text; no shell commands are executed.")
        elif _looks_int(default, key):
            value_type = "integer"
            control = "number"
            min_value = 0
            step = 1
            if key == "PORT":
                min_value = 1
                max_value = 65535
            elif "PRICE" in key and key.startswith("PAPER_"):
                max_value = 1
                step = 0.01
            elif "ROWS" in key or "RECORDS" in key:
                max_value = 10000000
            rules.append("Must be an integer inside the configured range.")
        elif _looks_float(default):
            value_type = "float"
            control = "number"
            min_value = 0
            step = 0.01
            if "PRICE" in key:
                max_value = 1
            rules.append("Must be a number inside the configured range.")
        elif key.endswith("ALLOWLIST") or key.endswith("ALLOWED_MARKET_IDS") or key.endswith("ALLOWED_DOMAINS") or default.find(",") >= 0:
            value_type = "list"
            control = "text"
            rules.append("Comma-separated list. Use an empty value to disable/clear the list.")
        else:
            rules.append("Free-form text is used only because no safer constrained control is available.")

        if affects_lan and key == "HOST":
            warnings.append("Binding to 0.0.0.0 exposes the console to other devices on the LAN.")
        if key == "ALLOWED_HOSTS":
            warnings.append("Using * is convenient for LAN demos but less restrictive than fixed hosts/IPs.")
        if key == "POLYMARKET_TRAINING_HOST_JOBS_ENABLED":
            warnings.append("Host jobs remain local and manual-review-only, but can consume CPU/memory when enabled.")
        if dangerous:
            warnings.append("Dangerous live/execution-facing setting. Requires explicit confirmation before saving an enabling value.")
            blockers.append(f"Enabling this key requires confirmation phrase: {CONFIG_CONFIRMATION_PHRASE}")
        if secret:
            warnings.append("Existing secret values are shown as masked placeholders only.")

        schema.append(
            ConfigOption(
                key=key,
                label=_label_for_key(key),
                description=description,
                help_text=help_text,
                group=group,
                value_type=value_type,
                control=control,
                default_value=default,
                allowed_values=allowed,
                recommended_values=allowed[:],
                min_value=min_value,
                max_value=max_value,
                step=step,
                restart_required=True,
                secret=secret,
                advanced=advanced,
                dangerous=dangerous,
                affects_live_trading=affects_live,
                affects_training_jobs=affects_training,
                affects_lan_exposure=affects_lan,
                validation_rules=rules,
                warning_messages=warnings,
                blocker_messages=blockers,
            )
        )
    return schema


def schema_by_key() -> dict[str, ConfigOption]:
    return {option.key: option for option in build_config_schema()}


def mask_value(key: str, value: Any, *, secret: bool | None = None) -> str:
    text = "" if value is None else str(value)
    is_secret = _is_secret_key(key) if secret is None else secret
    if not is_secret:
        return text
    if not text:
        return ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"***masked***:{digest}"


def config_status() -> dict[str, Any]:
    defaults = _example_values()
    dotenv = _dot_env_values()
    options = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    for option in build_config_schema():
        effective = _effective_value(option.key, dotenv, defaults)
        saved = dotenv.get(option.key, "")
        source = _source_for(option.key, dotenv, defaults)
        displayed = mask_value(option.key, effective, secret=option.secret)
        saved_displayed = mask_value(option.key, saved, secret=option.secret)
        item = asdict(option)
        item.update(
            {
                "current_value": displayed,
                "effective_value": displayed,
                "saved_env_value": saved_displayed,
                "raw_effective_value_present": bool(effective),
                "source": source,
                "differs_from_saved_env": option.key in os.environ and option.key in dotenv and os.environ.get(option.key, "") != dotenv.get(option.key, ""),
                "anchor": option.key.lower(),
            }
        )
        options.append(item)
        grouped.setdefault(option.group, []).append(item)
    validation = validate_config_values({})
    warnings.extend(validation.get("warnings", []))
    blockers.extend(validation.get("blockers", []))
    return {
        "app_version": APP_VERSION,
        "env_path": str(ENV_PATH),
        "env_present": ENV_PATH.exists(),
        "env_example_path": str(ENV_EXAMPLE_PATH),
        "env_example_present": ENV_EXAMPLE_PATH.exists(),
        "backup_dir": str(CONFIG_BACKUP_DIR),
        "audit_dir": str(CONFIG_AUDIT_DIR),
        "confirmation_phrase": CONFIG_CONFIRMATION_PHRASE,
        "option_count": len(options),
        "groups": grouped,
        "options": options,
        "warnings": warnings,
        "blockers": blockers,
        "manual_review_only": True,
        "can_live_trade": False,
    }


def _normalize_value(option: ConfigOption, value: Any) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    if value is None:
        value = ""
    if isinstance(value, list):
        if option.control == "multi_select":
            value = ",".join(str(v).strip() for v in value if str(v).strip())
        else:
            value = ",".join(str(v) for v in value)
    text = str(value).strip()

    if option.value_type == "boolean":
        lowered = text.lower()
        if lowered in TRUE_VALUES:
            return "true", warnings, blockers
        if lowered in FALSE_VALUES:
            return "false", warnings, blockers
        blockers.append(f"{option.key} must be true or false.")
        return text, warnings, blockers

    if option.value_type == "integer":
        try:
            number = int(float(text)) if text != "" else 0
        except ValueError:
            blockers.append(f"{option.key} must be an integer.")
            return text, warnings, blockers
        if option.min_value is not None and number < option.min_value:
            blockers.append(f"{option.key} must be >= {int(option.min_value)}.")
        if option.max_value is not None and number > option.max_value:
            blockers.append(f"{option.key} must be <= {int(option.max_value)}.")
        return str(number), warnings, blockers

    if option.value_type == "float":
        try:
            number = float(text) if text != "" else 0.0
        except ValueError:
            blockers.append(f"{option.key} must be a number.")
            return text, warnings, blockers
        if option.min_value is not None and number < option.min_value:
            blockers.append(f"{option.key} must be >= {option.min_value}.")
        if option.max_value is not None and number > option.max_value:
            blockers.append(f"{option.key} must be <= {option.max_value}.")
        return str(number).rstrip("0").rstrip(".") if "." in str(number) else str(number), warnings, blockers

    if option.value_type in {"enum"}:
        if option.allowed_values and text not in option.allowed_values:
            blockers.append(f"{option.key} must be one of: {', '.join(option.allowed_values)}.")
        return text, warnings, blockers

    if option.value_type == "multiselect":
        values = [item.strip() for item in text.split(",") if item.strip()]
        invalid = [item for item in values if option.allowed_values and item not in option.allowed_values]
        if invalid:
            blockers.append(f"{option.key} has invalid values: {', '.join(invalid)}.")
        return ",".join(values), warnings, blockers

    if option.value_type == "url" and text and not (text.startswith("http://") or text.startswith("https://")):
        warnings.append(f"{option.key} does not look like an http(s) URL.")
    if option.value_type == "path" and any(token in text for token in [";", "&&", "|", "`"]):
        blockers.append(f"{option.key} must be a plain filesystem path, not a shell command.")
    return text, warnings, blockers


def validate_config_values(changes: dict[str, Any] | None = None, *, confirmation: str = "") -> dict[str, Any]:
    changes = changes or {}
    schema = schema_by_key()
    defaults = _example_values()
    dotenv = _dot_env_values()
    merged = {key: _effective_value(key, dotenv, defaults) for key in schema}
    normalized_changes: dict[str, str] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    field_results: dict[str, dict[str, Any]] = {}

    unknown = [key for key in changes if key not in schema]
    for key in unknown:
        blockers.append(f"Unsupported key cannot be written through GUI: {key}")

    for key, raw in changes.items():
        if key not in schema:
            continue
        option = schema[key]
        if option.secret and str(raw or "") == "":
            # Blank masked secret forms mean preserve existing value.
            continue
        normalized, item_warnings, item_blockers = _normalize_value(option, raw)
        normalized_changes[key] = normalized
        merged[key] = normalized
        warnings.extend(item_warnings)
        blockers.extend(item_blockers)
        if option.dangerous and _bool_text(normalized) and confirmation != CONFIG_CONFIRMATION_PHRASE:
            blockers.append(f"{key} is dangerous/live-facing and requires confirmation phrase {CONFIG_CONFIRMATION_PHRASE}.")
        if key == "HOST" and normalized == "0.0.0.0":
            warnings.append("HOST=0.0.0.0 exposes the app to LAN devices; keep ALLOWED_HOSTS restrictive when possible.")
        if key == "ALLOWED_HOSTS" and normalized == "*":
            warnings.append("ALLOWED_HOSTS=* accepts any Host header; safe only for controlled local/LAN demos.")
        if key == "POLYMARKET_TRAINING_HOST_JOBS_ENABLED" and _bool_text(normalized):
            warnings.append("Host training jobs are enabled. Jobs remain local/manual-review-only but may consume CPU/RAM.")
        field_results[key] = {"normalized_value": mask_value(key, normalized, secret=option.secret), "warnings": item_warnings, "blockers": item_blockers}

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(float(merged.get(key, default) or default))
        except Exception:
            return default

    training_max = _int("POLYMARKET_TRAINING_MAX_ROWS")
    training_default = _int("POLYMARKET_TRAINING_DEFAULT_MAX_ROWS")
    training_hard = _int("POLYMARKET_TRAINING_HARD_MAX_ROWS")
    training_batch = _int("POLYMARKET_TRAINING_BATCH_SIZE")
    artifact_bytes = _int("POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES")
    if training_hard and training_max > training_hard:
        blockers.append("POLYMARKET_TRAINING_MAX_ROWS cannot exceed POLYMARKET_TRAINING_HARD_MAX_ROWS.")
    if training_hard and training_default > training_hard:
        blockers.append("POLYMARKET_TRAINING_DEFAULT_MAX_ROWS cannot exceed POLYMARKET_TRAINING_HARD_MAX_ROWS.")
    if training_batch <= 0:
        blockers.append("POLYMARKET_TRAINING_BATCH_SIZE must be positive.")
    if training_max and training_batch > training_max:
        blockers.append("POLYMARKET_TRAINING_BATCH_SIZE cannot exceed POLYMARKET_TRAINING_MAX_ROWS.")
    if artifact_bytes and artifact_bytes > 250000000:
        warnings.append("POLYMARKET_TRAINING_MAX_ARTIFACT_BYTES is very large; ensure disk space is available.")
    if _bool_text(merged.get("TRAINING_ALLOW_LIVE_EXECUTION")):
        blockers.append("TRAINING_ALLOW_LIVE_EXECUTION must remain false in this safety posture.")
    if not _bool_text(merged.get("TRAINING_OUTPUTS_MANUAL_REVIEW_ONLY", "true")):
        blockers.append("TRAINING_OUTPUTS_MANUAL_REVIEW_ONLY must remain true.")
    if _bool_text(merged.get("POLYMARKET_LIVE_ENABLE_AUTONOMOUS")):
        blockers.append("POLYMARKET_LIVE_ENABLE_AUTONOMOUS is blocked by this package safety posture.")

    return {
        "ok": not blockers,
        "normalized_changes": normalized_changes,
        "field_results": field_results,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
        "manual_review_only": True,
        "can_live_trade": False,
    }


def preview_config_diff(changes: dict[str, Any] | None = None, *, confirmation: str = "", preset_id: str | None = None) -> dict[str, Any]:
    changes = changes or {}
    schema = schema_by_key()
    defaults = _example_values()
    dotenv = _dot_env_values()
    validation = validate_config_values(changes, confirmation=confirmation)
    normalized = validation.get("normalized_changes", {})
    rows = []
    for key, new_value in normalized.items():
        option = schema[key]
        old_value = _effective_value(key, dotenv, defaults)
        saved_value = dotenv.get(key, "")
        rows.append(
            {
                "key": key,
                "label": option.label,
                "old_displayed_value": mask_value(key, old_value, secret=option.secret),
                "saved_env_value": mask_value(key, saved_value, secret=option.secret),
                "new_displayed_value": mask_value(key, new_value, secret=option.secret),
                "source": _source_for(key, dotenv, defaults),
                "restart_required": option.restart_required,
                "warnings": option.warning_messages,
                "blockers": option.blocker_messages if option.dangerous and _bool_text(new_value) and confirmation != CONFIG_CONFIRMATION_PHRASE else [],
                "dangerous": option.dangerous,
                "secret": option.secret,
            }
        )
    return {"ok": validation["ok"], "preset_id": preset_id or "", "diff": rows, "validation": validation, "restart_required": bool(rows)}


def _quote_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _write_env(normalized_changes: dict[str, str]) -> Path | None:
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    rows, existing = _parse_env_lines(ENV_PATH)
    backup_path: Path | None = None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if ENV_PATH.exists():
        backup_path = CONFIG_BACKUP_DIR / f"env_backup_{timestamp}.env"
        shutil.copy2(ENV_PATH, backup_path)
    else:
        ENV_PATH.write_text("# Polymarket Gamma Starter local configuration\n", encoding="utf-8")
        rows, existing = _parse_env_lines(ENV_PATH)

    remaining = dict(normalized_changes)
    output_lines: list[str] = []
    for row in rows:
        if row.get("type") == "assignment" and row.get("key") in remaining:
            key = row["key"]
            output_lines.append(f"{key}={_quote_env_value(remaining.pop(key))}")
        else:
            output_lines.append(row.get("raw", ""))
    if remaining:
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.append("# Added by GUI-first configuration console")
        for key, value in remaining.items():
            output_lines.append(f"{key}={_quote_env_value(value)}")
    ENV_PATH.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    return backup_path


def save_config_changes(changes: dict[str, Any] | None = None, *, confirmation: str = "", requested_by: str = "local", preset_id: str | None = None) -> dict[str, Any]:
    diff = preview_config_diff(changes, confirmation=confirmation, preset_id=preset_id)
    if not diff.get("ok"):
        return {"ok": False, "saved": False, **diff}
    normalized = diff["validation"].get("normalized_changes", {})
    backup_path = _write_env(normalized)
    CONFIG_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit = {
        "timestamp": now_iso(),
        "app_version": APP_VERSION,
        "requested_by": requested_by,
        "preset_id": preset_id or "",
        "changed_keys": list(normalized),
        "diff": diff.get("diff", []),
        "validation_status": "ok",
        "warnings": diff["validation"].get("warnings", []),
        "blockers": diff["validation"].get("blockers", []),
        "backup_file": str(backup_path) if backup_path else "",
        "manual_confirmation_supplied": confirmation == CONFIG_CONFIRMATION_PHRASE,
        "manual_review_only": True,
        "can_live_trade": False,
    }
    audit_path = CONFIG_AUDIT_DIR / f"config_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    return {"ok": True, "saved": True, "backup_file": str(backup_path) if backup_path else "", "audit_file": str(audit_path), **diff}


def _requirement_names() -> list[str]:
    names: list[str] = []
    req_path = PROJECT_ROOT / "requirements.txt"
    for line in _read_text(req_path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=~!\[]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name.replace("-", "_"))
    return names


def setup_runtime_status() -> dict[str, Any]:
    defaults = _example_values()
    dotenv = _dot_env_values()
    dependency_rows = []
    for name in _requirement_names():
        import_name = {"python_dotenv": "dotenv", "fastapi": "fastapi", "uvicorn": "uvicorn", "httpx": "httpx", "jinja2": "jinja2", "rich": "rich"}.get(name.lower(), name)
        dependency_rows.append({"name": name, "import_name": import_name, "available": importlib.util.find_spec(import_name) is not None})
    venv_detected = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    current_differs = []
    for key, saved in dotenv.items():
        if key in os.environ and os.environ.get(key, "") != saved:
            current_differs.append({"key": key, "process_value": mask_value(key, os.environ.get(key, "")), "saved_env_value": mask_value(key, saved)})
    return {
        "app_version": APP_VERSION,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "virtual_environment_detected": venv_detected,
        "sys_prefix": sys.prefix,
        "sys_base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "dependency_status": dependency_rows,
        "expected_launch_command": "python -m uvicorn app.main:app --host ${HOST:-127.0.0.1} --port ${PORT:-8000}",
        "recommended_venv_commands": ["python -m venv .venv", "source .venv/bin/activate  # Windows: .venv\\Scripts\\activate", "python -m pip install -r requirements.txt", "python run.py"],
        "current_working_directory": str(Path.cwd()),
        "project_root": str(PROJECT_ROOT),
        "runtime_data_directory": str(DATA_DIR),
        "env_path": str(ENV_PATH),
        "env_present": ENV_PATH.exists(),
        "env_example_path": str(ENV_EXAMPLE_PATH),
        "env_example_present": ENV_EXAMPLE_PATH.exists(),
        "package_mode": "source_tree" if (PROJECT_ROOT / "app").exists() else "unknown",
        "platform": platform.platform(),
        "restart_required_after_save": True,
        "process_differs_from_saved_env": current_differs,
        "manual_review_only": True,
        "can_live_trade": False,
    }


def config_presets() -> list[dict[str, Any]]:
    return [
        {
            "preset_id": "locked_down_safe_mode",
            "label": "Locked-down safe mode",
            "description": "Local-only, read-only, training host jobs off, internet ingestion off, live execution disabled.",
            "changes": {"HOST": "127.0.0.1", "READ_ONLY": "true", "LIVE_TRADING_ENABLED": "false", "POLYMARKET_DATA_ALLOW_INTERNET": "false", "POLYMARKET_TRAINING_HOST_JOBS_ENABLED": "false", "POLYMARKET_LIVE_ALLOW_REAL_NETWORK": "false", "POLYMARKET_LIVE_ENABLE_SUBMIT": "false", "POLYMARKET_LIVE_ENABLE_CANCEL": "false", "POLYMARKET_LIVE_ENABLE_AUTONOMOUS": "false"},
        },
        {
            "preset_id": "local_demo_mode",
            "label": "Local demo mode",
            "description": "Local web UI, read-only defaults, paper/data/training pages visible, no live execution.",
            "changes": {"HOST": "127.0.0.1", "APP_MODE": "read_only", "READ_ONLY": "true", "LIVE_TRADING_ENABLED": "false", "TRAINING_LAB_ENABLED": "true", "POLYMARKET_TRAINING_HOST_JOBS_ENABLED": "false", "POLYMARKET_DATA_ALLOW_INTERNET": "false"},
        },
        {
            "preset_id": "lan_demo_mode",
            "label": "LAN demo mode",
            "description": "Expose the console on the LAN while keeping live trading disabled.",
            "changes": {"HOST": "0.0.0.0", "ALLOWED_HOSTS": "*", "SESSION_COOKIE_SECURE": "false", "LIVE_TRADING_ENABLED": "false", "POLYMARKET_LIVE_ALLOW_REAL_NETWORK": "false", "POLYMARKET_LIVE_ENABLE_SUBMIT": "false", "POLYMARKET_LIVE_ENABLE_CANCEL": "false"},
        },
        {
            "preset_id": "paper_trading_only",
            "label": "Paper trading only",
            "description": "Enable local paper workflow posture while keeping all live execution gates disabled.",
            "changes": {"APP_MODE": "paper", "READ_ONLY": "true", "LIVE_TRADING_ENABLED": "false", "LIVE_DRY_RUN_ONLY": "true", "LIVE_REQUIRE_MANUAL_APPROVAL": "true", "POLYMARKET_LIVE_KILL_SWITCH": "true", "POLYMARKET_LIVE_ENABLE_SUBMIT": "false", "POLYMARKET_LIVE_ENABLE_CANCEL": "false"},
        },
        {
            "preset_id": "data_ingestion_mode",
            "label": "Data ingestion mode",
            "description": "Prepare local/internet data ingestion controls while requiring operator confirmation and allowlists.",
            "changes": {"POLYMARKET_DATA_ALLOW_NETWORK": "false", "POLYMARKET_DATA_ALLOW_INTERNET": "false", "POLYMARKET_DATA_REQUIRE_OPERATOR_CONFIRMATION": "true", "POLYMARKET_DATA_MAX_REQUESTS_PER_RUN": "25", "POLYMARKET_DATA_STORE_RAW_RESPONSES": "false"},
        },
        {
            "preset_id": "training_backtesting_mode",
            "label": "Training and backtesting mode",
            "description": "Enable Training Lab with manual-review-only outputs and default local caps.",
            "changes": {"TRAINING_LAB_ENABLED": "true", "TRAINING_OUTPUTS_MANUAL_REVIEW_ONLY": "true", "TRAINING_ALLOW_LIVE_EXECUTION": "false", "POLYMARKET_TRAINING_HOST_JOBS_ENABLED": "false", "POLYMARKET_TRAINING_MAX_ROWS": "100000", "POLYMARKET_TRAINING_BATCH_SIZE": "5000"},
        },
        {
            "preset_id": "host_training_100k_mode",
            "label": "100K host training mode",
            "description": "Enable local host training jobs with 100K default row caps, 5K batches, and manual-review-only signal previews.",
            "changes": {"POLYMARKET_TRAINING_HOST_JOBS_ENABLED": "true", "POLYMARKET_TRAINING_MAX_ROWS": "100000", "POLYMARKET_TRAINING_DEFAULT_MAX_ROWS": "100000", "POLYMARKET_TRAINING_HARD_MAX_ROWS": "1000000", "POLYMARKET_TRAINING_BATCH_SIZE": "5000", "POLYMARKET_TRAINING_BLOCK_OVER_HARD_MAX_ROWS": "true", "POLYMARKET_TRAINING_MAX_RUNTIME_SECONDS": "900", "TRAINING_OUTPUTS_MANUAL_REVIEW_ONLY": "true", "TRAINING_ALLOW_LIVE_EXECUTION": "false"},
        },
        {
            "preset_id": "live_readiness_review_mode",
            "label": "Live-readiness review mode",
            "description": "Show live-readiness checks and dry-run review while keeping real network submit/cancel disabled.",
            "changes": {"LIVE_DRY_RUN_ONLY": "true", "LIVE_REQUIRE_MANUAL_APPROVAL": "true", "LIVE_PRETRADE_CHECKS_ENABLED": "true", "LIVE_AUDIT_REQUIRED": "true", "POLYMARKET_LIVE_KILL_SWITCH": "true", "POLYMARKET_LIVE_ALLOW_REAL_NETWORK": "false", "POLYMARKET_LIVE_ENABLE_SUBMIT": "false", "POLYMARKET_LIVE_ENABLE_CANCEL": "false"},
        },
        {
            "preset_id": "manual_live_execution_readiness_mode",
            "label": "Manual live execution readiness mode",
            "description": "Keep execution-facing gates fail-closed while preparing manual authorization/dry-run records.",
            "changes": {"POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED": "false", "POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED": "false", "POLYMARKET_LIVE_REQUIRE_MANUAL_AUTH": "true", "POLYMARKET_LIVE_REQUIRE_DRY_RUN_RECEIPT": "true", "POLYMARKET_LIVE_KILL_SWITCH": "true", "POLYMARKET_LIVE_ALLOW_REAL_NETWORK": "false", "POLYMARKET_LIVE_ENABLE_SUBMIT": "false", "POLYMARKET_LIVE_ENABLE_CANCEL": "false"},
        },
    ]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    for preset in config_presets():
        if preset["preset_id"] == preset_id:
            return preset
    return None


def preset_diff(preset_id: str, *, confirmation: str = "") -> dict[str, Any]:
    preset = get_preset(preset_id)
    if not preset:
        return {"ok": False, "preset_id": preset_id, "diff": [], "validation": {"ok": False, "blockers": ["Unknown preset"], "warnings": []}}
    return preview_config_diff(preset["changes"], confirmation=confirmation, preset_id=preset_id)


def apply_preset(preset_id: str, *, confirmation: str = "", requested_by: str = "local") -> dict[str, Any]:
    preset = get_preset(preset_id)
    if not preset:
        return {"ok": False, "saved": False, "validation": {"ok": False, "blockers": ["Unknown preset"], "warnings": []}}
    return save_config_changes(preset["changes"], confirmation=confirmation, requested_by=requested_by, preset_id=preset_id)


def export_sanitized_configuration() -> dict[str, Any]:
    status = config_status()
    setup = setup_runtime_status()
    return {
        "generated_at": now_iso(),
        "app_version": APP_VERSION,
        "configuration": status,
        "setup_runtime_status": setup,
        "manual_review_only": True,
        "can_live_trade": False,
        "note": "Secrets are masked. Runtime data and artifacts are not included.",
    }


def sanitized_env_template() -> str:
    lines = ["# Sanitized Polymarket Gamma Starter .env template", f"# Generated at {now_iso()}", "# Secrets are intentionally blank/masked. Review before use.", ""]
    for option in build_config_schema():
        value = "" if option.secret else option.default_value
        lines.append(f"# {option.label}: {option.description}")
        lines.append(f"{option.key}={_quote_env_value(value)}")
        lines.append("")
    return "\n".join(lines)
