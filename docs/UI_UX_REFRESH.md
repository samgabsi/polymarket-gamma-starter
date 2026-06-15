# UI/UX Refresh

Version: v0.9.0-real

Polymarket Gamma Starter v0.8.0-real reorganizes the existing local research, paper workflow, live-readiness, manual boundary, and audit surfaces into a more coherent operator console. This is a presentation and workflow-clarity release. It does not add autonomous trading, live signing, live order submission, live cancellation, wallet access, or network execution behavior.

## Goals

- Make the app feel like one staged console instead of many isolated pages.
- Keep paper-only, live-readiness-only, fake-local, and live-disabled states visible.
- Improve navigation so operators can move from research to paper tickets, risk review, approvals, closeout, live-readiness review, manual boundary checks, and audit records.
- Standardize cards, badges, callouts, tables, forms, empty states, metadata grids, and action bars.
- Preserve all existing URLs, APIs, CSV exports, CLI commands, local ledgers, and safety gates.

## App Shell

The shared shell adds:

- grouped sidebar navigation,
- active page indication,
- top header with app name, current version, and safety badges,
- breadcrumbs on migrated pages,
- consistent footer posture,
- responsive layout for narrow browser panes,
- skip link and visible keyboard focus states.

Navigation groups:

- Overview
- Research
- Paper Workflow
- Risk / Ops
- Live Readiness
- Manual Boundary
- Audit / Reports
- Settings / Config

## Dashboard

The home route `/` is now an operator overview. It summarizes:

- system posture and version,
- paper ticket state,
- pending approvals,
- paper preflight state,
- closeout state,
- live configuration readiness,
- live adapter and manual execution boundary posture,
- execution attempts,
- audit categories,
- recommended next operator actions.

The dashboard is intended to answer: "What should I look at next?"

## Workflow Map

The new `/workflow` route is a read-only stage navigator. It links the existing workflow stages:

- Research
- Readiness
- Playbook
- Paper Ticket
- Paper Approval
- Paper Preflight
- Execution Queue
- Ops Closeout
- Live Config
- Live Intent
- Live Preflight
- Operator Authorization
- Execution Packet
- Dry-Run Adapter
- Adapter Request
- Manual Execution Review
- Manual Execution Control
- Audit / Closeout

The JSON version is available at `/api/ui/workflow`.

## UI System

The new `/ui-system` route documents local visual primitives for future templates:

- status badges,
- safety callouts,
- cards,
- metadata grids,
- table wrappers,
- form controls,
- empty states,
- destructive and disabled action language.

## Safety Posture

The UI refresh keeps the live boundary unchanged:

- no autonomous execution loops,
- no order signing,
- no wallet interaction,
- no real submit/cancel network requests,
- fake adapter receipts remain local simulations only,
- kill switch, manual approval, dry-run, preflight, audit, and authorization gates remain visible.

## Implementation Notes

- Styling remains plain CSS in `app/static/style.css`.
- Templates remain server-rendered Jinja templates.
- No frontend framework, external CDN, or build pipeline was added.
- Existing pages that were not fully migrated still remain reachable through the grouped navigation.
