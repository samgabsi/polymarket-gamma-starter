# Settings Guide — v2.1.0-real

Live v2 settings are grouped for operator readability at `/v2-live/settings`.

## Sections

- General
- Trading Mode
- API Hosts
- Credentials / Secrets
- Live Trading Gates
- Risk Limits
- Order Defaults
- Audit / Exports
- Advanced / Debug

The page is a safe map and validator. It does not write secrets or silently mutate `.env`.

## Validation endpoint

`POST /api/v2/live/settings/validate` accepts a small JSON object of candidate values and returns:

- `valid`
- `errors`
- `warnings`
- `secret_values_returned=false`

Use the full configuration console at `/settings/configuration` when you want to apply changes through the existing audited settings workflow.
