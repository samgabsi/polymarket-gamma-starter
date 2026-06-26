# AI Prompt Governance Guide - v4.5.0-real

Prompt governance templates define draft-only purposes, redaction rules, provider boundaries, evidence requirements, citation requirements, market-implied comparison disclaimers, calibration limitations, and export safety rules.

v4.5 prompt governance must preserve these rules for market-row AI Edge packets:

- label model fair estimates as estimates, not truth
- label market-implied comparisons as approximate unless executable-side pricing is explicitly available
- keep favorite ranking separate from edge
- do not create trade approvals or executable orders
- do not include secrets in prompts or outputs


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
