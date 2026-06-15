# Internet-to-Training Workflow

The v1.5.0 workflow is guidance/status only. The operator explicitly triggers each action:

1. Register internet source.
2. Validate source.
3. Preview ingestion.
4. Run ingestion only after gates pass.
5. Review raw snapshot.
6. Normalize records.
7. Generate/review labels.
8. Build a manifest-backed dataset.
9. Preview a host training job.
10. Start the host job only when enabled.
11. Review metrics/artifacts.
12. Register model metadata.
13. Queue generated signals for manual review.

No workflow step trades, cancels, signs orders, or bypasses live safety gates.
