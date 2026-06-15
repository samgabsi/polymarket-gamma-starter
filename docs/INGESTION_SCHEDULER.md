# Internet Ingestion Scheduler

The internet ingestion scheduler registry exists for planning, visibility, and due-job previewing. It is disabled by default through `POLYMARKET_DATA_INGESTION_SCHEDULER_ENABLED=false`.

No daemon starts on app boot. Schedules do not run unless global and per-source gates are explicitly enabled by the operator.
