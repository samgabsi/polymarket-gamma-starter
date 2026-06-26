# AI Evidence Packet Guide - v4.4.0-real

AI evidence packets normalize source URLs, snippets, citation metadata, source quality, recency, relevance, contradiction notes, and missing-information notes for AI Edge Research.

## Evidence Source Fields

- source ID
- title
- URL or supplied source reference
- publisher or domain
- published timestamp when available
- retrieved timestamp
- source type
- quality, recency, and relevance labels
- summary and key claims
- supports, contradicts, or mixed stance
- limitations

## Safety Rules

Evidence packets are human-review inputs. They do not become trade approvals, order signals, order payloads, cancellation instructions, live-trading arm requests, task approvals, or safety-gate bypasses.

Private keys, API keys, auth headers, wallet secrets, session cookies, passwords, and sensitive account data are redacted before prompt construction. Raw prompts and raw responses are not stored by default.

## Routes

- `GET /api/v3/ai/edge/evidence`
- `POST /api/v3/ai/edge/evidence/normalize`
- `GET /api/v3/ai/edge/evidence/export.json`
- `GET /api/v3/ai/edge/evidence/export.md`
- `GET /api/v3/ai/edge/evidence/export.csv`

Runtime evidence records live under `data/ai/edge/` after explicit operator action and are excluded from release ZIPs.
