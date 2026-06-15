# Dataset Manifests

Dataset manifests make a built dataset reproducible. They record source IDs, snapshot hashes, label configuration, feature configuration, split method, filters, row counts, schema hash, content hash, build time, software version, warnings, and blockers.

Use `/api/training/dataset-builds/{dataset_build_id}/manifest` or `--training-dataset-build-manifest --dataset-build-id ...` to inspect a manifest.
