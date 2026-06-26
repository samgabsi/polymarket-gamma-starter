# AI Edge Privacy and Safety Guide - v4.5.0-real

AI Edge market-row packets must redact secrets, keep prompts/responses safe for audit, and never become live orders or approvals.

# AI Safety and Privacy Guide - v4.5.0-real

v4.5 continues the no-secret, no-live-mutation AI boundary. AI Edge, OpenAI, local LLMs, exports, docs, screenshots, prompt governance, and audit records must not expose private keys, wallet secrets, auth headers, session cookies, API keys, passwords, local credentials, or sensitive account data.

## Required AI Boundaries

- AI output is draft research only.
- AI cannot approve trades.
- AI cannot place or cancel orders.
- AI cannot arm live trading or disable read-only mode.
- AI cannot disable the kill switch.
- AI cannot bypass deterministic backend gates.
- AI cannot convert recommendations into accepted tasks or orders without explicit human action in safe workflows.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
