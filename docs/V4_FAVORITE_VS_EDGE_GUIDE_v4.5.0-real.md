# Favorite vs Edge Guide - v4.5.0-real

v4.5 makes the favorite/edge distinction visible in the market table and details views.


## Favorite vs Edge

Favorite means the highest-probability outcome in a detected group, such as a World Cup winner family. Edge means a possible model/price mismatch versus the current market YES or NO price. A favorite can have no edge if the price is already too high. A long shot can have edge if the price is too low. Group rank never means a trade is approved.


## Example

A row can show France at YES 18.0 percent and rank #1 by market YES price among detected World Cup winner markets. If the model fair YES estimate is 20.5 percent, the YES edge is +2.5 percentage points and the draft recommended side may be YES. This does not mean France is guaranteed to win. It only means the review model currently estimates fair YES above the displayed YES price.

For a NO edge, if the market YES price is 18.0 percent and model fair YES is 12.0 percent, then model fair NO is 88.0 percent. If the market NO price is 82.0 percent, the draft NO edge is +6.0 percentage points.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
