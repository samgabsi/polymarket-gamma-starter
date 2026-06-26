# Market Family Ranking Guide - v4.5.0-real

Market-family ranking is a conservative UI/research aid for mutually exclusive market groups.

## Detection Rules

The detector in `app/market_edge.py` uses title and slug patterns only when confidence is high enough. Examples include:

- `Will France win the 2026 FIFA World Cup?`
- `Will Brazil win the 2026 FIFA World Cup?`
- `Will Germany win the 2026 FIFA World Cup?`

These rows can be grouped as `2026 FIFA World Cup winner`. Similar conservative patterns are available for tournament winners, election winners, award winners, and championship winners. Unrelated markets are not forced into a family and the UI shows `No family detected` when grouping is unavailable.

## Ranking

Family rows can be ranked by market YES price and, when model fair probability is available, by model fair YES probability. The UI can show Group favorite, Rank #1 by market YES price, Rank #2 by model fair probability, or Not favorite but possible edge.


## Favorite vs Edge

Favorite means the highest-probability outcome in a detected group, such as a World Cup winner family. Edge means a possible model/price mismatch versus the current market YES or NO price. A favorite can have no edge if the price is already too high. A long shot can have edge if the price is too low. Group rank never means a trade is approved.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
