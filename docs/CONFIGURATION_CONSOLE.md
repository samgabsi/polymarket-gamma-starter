# GUI-first Configuration Console v1.8.0-real

The GUI-first configuration console turns supported operator-facing `.env` settings into guided UI controls at `/settings/configuration` and `/setup/environment`.

The design goal is to avoid raw `.env` editing where a safer control is possible. Boolean values render as toggles, short enumerations render as radio groups, larger enumerations render as dropdowns, supported allowlists render as checkbox multi-selects, row caps and limits render as numeric inputs, paths render as path text fields, and credentials render as masked secret fields. Plain text is used only where a constrained control would be misleading, such as custom hostnames, URLs, paths, labels, allowlists, and advanced override text.

## What the schema tracks

Every schema-backed option includes the env key, display label, description, help text, group, current effective value, saved `.env` value, default, control type, validation rules, restart-required flag, secret/advanced/dangerous flags, and whether the option affects live readiness, training jobs, or LAN exposure.

The schema is implemented in `app/config_console.py` and is used by the GUI, APIs, CLI commands, validation, diff previews, and sanitized exports.

## Safe .env write behavior

The console can read and write supported keys only. Unknown keys and comments are preserved where practical. Saving creates a timestamped backup under `data/config_backups/` and writes an audit record under `data/config_audit/`. Both paths are runtime-only and must not be included in release ZIPs.

Secrets are masked in the UI, sanitized exports, and audit records. Blank secret fields preserve the currently saved value.

## Diff and validation

Before saving, operators should preview the diff. Diff rows show the key, old displayed value, new displayed value, source, restart requirement, and dangerous/secret flags. Blockers prevent saving. Warnings are shown for LAN exposure, host training enablement, large artifact limits, and live/execution-facing settings.

Dangerous live/execution-facing enabling changes require the confirmation phrase:

`I_UNDERSTAND_CONFIG_CAN_CHANGE_SAFETY_POSTURE`

Training output safety is enforced. `TRAINING_OUTPUTS_MANUAL_REVIEW_ONLY` must stay true and `TRAINING_ALLOW_LIVE_EXECUTION` must stay false.

## API routes

- `GET /api/config/schema`
- `GET /api/config/status`
- `POST /api/config/validate`
- `POST /api/config/diff`
- `POST /api/config/save`
- `GET /api/config/export-sanitized`
- `GET /api/config/export-sanitized.env`
- `GET /api/config/presets`
- `POST /api/config/presets/{preset_id}/preview`
- `POST /api/config/presets/{preset_id}/apply`
- `GET /api/setup/status`

## CLI routes

```bash
python -m app.cli --config-schema
python -m app.cli --config-status
python -m app.cli --config-validate --config-changes '{"POLYMARKET_TRAINING_MAX_ROWS":"100000"}'
python -m app.cli --config-diff --config-changes '{"POLYMARKET_TRAINING_HOST_JOBS_ENABLED":"true"}'
python -m app.cli --config-export-sanitized
python -m app.cli --config-presets
python -m app.cli --setup-status
```

Use `--config-save` only after reviewing the diff. It writes `.env`, backup, and audit files locally.
