# UI/UX System

Version 1.4.0 introduces a responsive operator-console layout designed for desktop, tablet, mobile browser, and narrow browser side panels.

## Goals

- Keep every existing backend/API/CLI workflow intact.
- Make pages easier to read on small screens.
- Keep safety posture visible across the console.
- Make dangerous live actions visually distinct from read-only status and preview flows.
- Improve empty states and next-step guidance without enabling automation.

## Shared components

The shared base template now provides:

- desktop sidebar navigation,
- collapsible mobile navigation,
- global safety banner,
- quick action chips,
- responsive cards,
- responsive table wrappers,
- shared status badges,
- shared empty-state styling,
- touch-friendly controls.

## Safety rule

The UI is presentation and navigation only. It does not bypass backend checks for kill switch, live mode, real network permission, submit/cancel enablement, credentials, allowlists, notional limits, confirmations, audit logging, or operator approval.
