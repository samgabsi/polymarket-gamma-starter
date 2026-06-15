#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m app.cli --opportunities --snapshot --limit "${1:-100}"
