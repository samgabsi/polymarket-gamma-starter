# Data Source Registry

The source registry describes where data comes from. Supported source types include Gamma/CLOB metadata, local custom CSV/JSON, paper workflow exports, live/fake ledger exports, execution-quality simulations, and strategy-signal history.

Fields include source ID, name, source type, mode, network-required flag, enabled flag, scheduler flag, local path or endpoint name, last run status, warnings, blockers, and notes.

Network sources are registered disabled by default. Schedulers are forced off in this release.
