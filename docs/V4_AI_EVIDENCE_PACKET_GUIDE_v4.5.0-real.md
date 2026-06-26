# AI Evidence Packet Guide - v4.5.0-real

Evidence packets collect app-provided source summaries, citation labels, source metadata, contradictions, missing-information notes, freshness notes, and optional draft fair probability estimates.

## v4.5 Row Wiring

Market rows now provide AI Edge actions that can open or create a packet prefilled with the visible market context. Evidence links appear only when packet/evidence context is available. If evidence is missing, the row should show unavailable/needs review rather than inventing source claims.

No private keys, auth headers, session cookies, API keys, passwords, wallet secrets, or local credentials should be sent to OpenAI, local LLMs, exports, docs, screenshots, or audit records.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
