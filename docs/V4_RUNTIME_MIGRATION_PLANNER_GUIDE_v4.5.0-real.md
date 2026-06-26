# Runtime Migration Planner Guide - v4.5.0-real

The runtime migration planner remains dry-run-only. v4.5 does not require automatic runtime migration. Market-edge helpers operate on available market objects and do not rewrite stored runtime packets.

Migration plans must not move, delete, rewrite, copy, or export runtime data automatically.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
