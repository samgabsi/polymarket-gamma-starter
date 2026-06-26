# Manual QA Checklist - v4.5.0-real

## Navigation

- Verify the sidebar renders one Unified Surface group.
- Verify aliases `/operator-os`, `/ai`, `/edge`, `/platform`, `/live`, `/workspace`, `/tasks`, `/cockpit`, and `/routes` resolve without bypassing safety gates.
- Verify System Map lists AI Edge and market recommendation surfaces.

## Market Recommendations

- Verify a YES edge row says Recommended: YES and explains model fair YES vs market YES.
- Verify a NO edge row says Recommended: NO and explains model fair NO vs market NO.
- Verify close/noisy data says HOLD or NO CLEAR EDGE.
- Verify missing fair probability says INSUFFICIENT DATA.
- Verify favorite rank is separate from recommended side.
- Verify stale, liquidity, volume, or evidence warnings are visible where available.

## AI Edge

- Verify Analyze with AI Edge opens review-only packet context.
- Verify Open Packet, Evidence, and Calibration links do not place or cancel orders.
- Verify market-family comparison is labelled as research-only.

## Safety

- Verify read-only mode blocks live submits.
- Verify kill switch blocks live submits.
- Verify paper mode avoids live endpoints.
- Verify typed live-order confirmation remains required.
- Verify task completion and guided review completion do not approve trades.


## Safety and Scope

All edge, AI Edge, evidence, calibration, family-ranking, and recommendation output is draft research only. It is not financial advice, not a trade approval, and not an executable order. The release does not place orders, cancel orders, arm live trading, disable read-only mode, disable the kill switch, or let AI bypass backend gates. Live controls, paper controls, approval checkboxes, typed confirmation phrases, warning acknowledgements, audit logging, emergency controls, and kill-switch controls remain authoritative.
