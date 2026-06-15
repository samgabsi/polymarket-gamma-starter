# Mobile Operator Console

The v1.4.0 console is designed to be usable from a phone or tablet on the local LAN.

## Mobile navigation

On narrow screens, the desktop sidebar collapses into a `Menu · Safety · Workflows` panel. The menu groups the same operator workflows without removing routes or backend behavior.

## Global safety banner

Every console page shows the current safety posture:

- LIVE DISABLED / LIVE ENABLED
- REAL NETWORK DISABLED / ENABLED
- KILL SWITCH ACTIVE / OFF
- SUBMIT DISABLED / ENABLED
- CANCEL DISABLED / ENABLED
- AUTONOMOUS OFF / ENABLED
- DATA INGESTION LOCAL ONLY / NETWORK ENABLED

The banner is UI-only and does not call remote services by default.

## Tables on small screens

Wide tables remain inside horizontal scroll wrappers with a mobile hint. Records are still rendered safely when empty or malformed, and pages should not require horizontal page scrolling outside of table wrappers.

## Dangerous actions

Live-submit/cancel controls remain visually separate and backend-gated. The mobile UI must not make dangerous operations easier to trigger accidentally.

## v1.5.0 Internet ingestion and host training jobs

This release adds an operator-controlled internet ingestion and host training job runner milestone. Internet ingestion is disabled by default, requires approved sources and allowlisted domains, and is limited to public/read-only data fetches. Data ingestion does not trade. Host training jobs are disabled by default, use approved internal job types only, and write artifacts to runtime data directories that are excluded from release ZIPs. Training outputs remain manual-review-only and do not directly live-trade.
