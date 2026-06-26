# Operator Notes - v4.14.0-real

## Completed Workflow

The completed workflow is Opportunity Review / Operator Action audit hardening.

Operators can now:

- Open `/v3/opportunities`.
- Select Demo fixtures or Configured local/live source through an explicit data-mode selector.
- See top-level and row-level data state before making review decisions.
- Save operator notes with source route/component and data-state metadata.
- Send a market to watchlist or paper review, reject it, or archive it from browser POST forms.
- Open market detail and inspect previous/new state, source component, and data state in the audit history.
- Use the JSON notes/status APIs with the same source metadata.

## Operator Boundary

Opportunity review records are local evidence, not execution instructions. Review decisions are local workflow state, not trade approval. Live execution remains governed by separate fail-closed backend gates.

