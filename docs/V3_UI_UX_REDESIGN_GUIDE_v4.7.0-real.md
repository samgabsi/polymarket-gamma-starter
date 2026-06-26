# V3 UI/UX Redesign Guide - v4.7.0-real

This compatibility guide records the v3 command-center UI posture carried forward into v4.7.

## Scope

- Preserve the v3 operator command center, search, graph, workflow, cockpit, workspace, task, dataset, freshness, simulation, and analytics surfaces.
- Keep redesigned UI routes review-only and separate from live order submission, cancellation, approval, and live-trading arming.
- Continue to use `v3_design.css` and the existing authenticated page shell for v3 operator workflows.
- Treat generated screenshots as local QA artifacts only; do not include screenshots with secrets in release packages.

## Safety

The redesigned UI is a navigation and review surface. It does not bypass backend gates, disable read-only mode, disable kill switches, place orders, cancel orders, approve trades, or arm live trading.

