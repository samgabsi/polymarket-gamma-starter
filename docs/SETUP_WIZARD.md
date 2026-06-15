# Setup Wizard v1.8.0-real

The setup wizard at `/setup/wizard` offers safe presets for common operating modes. The wizard previews `.env` changes before writing and uses the same validation engine as the full configuration console.

## Presets

- Locked-down safe mode
- Local demo mode
- LAN demo mode
- Paper trading only
- Data ingestion mode
- Training and backtesting mode
- 100K host training mode
- Live-readiness review mode
- Manual live execution readiness mode

Each preset explains what it enables, what it does not enable, whether LAN exposure is involved, whether host training jobs or internet ingestion are changed, and whether live-readiness gates are touched.

## 100K host training through the GUI

Open `/setup/wizard`, select `100K host training mode`, preview the diff, and apply after validation. This preset sets local host training caps such as 100,000 max/default rows, a 1,000,000 hard cap, 5,000-row batches, runtime caps, and `TRAINING_ALLOW_LIVE_EXECUTION=false`.

Host training remains local and manual-review-only. It cannot place orders, cancel orders, sign messages, or touch wallets.
