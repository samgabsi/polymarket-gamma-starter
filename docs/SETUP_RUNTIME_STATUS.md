# Runtime and Virtual Environment Status v1.8.0-real

The runtime status page at `/setup/status` is a read-only setup diagnostic surface. It shows Python version, app version, venv detection, dependency availability, launch command, current working directory, project root, runtime data directory, `.env` path, `.env.example` path, platform, and process-vs-saved `.env` differences.

The page intentionally does not execute shell commands, run `pip`, mutate a virtual environment, install packages, or evaluate arbitrary user input. It only displays copyable commands that the operator may run manually in a terminal.

Runtime status is also available at:

```bash
python -m app.cli --setup-status
```

and:

`GET /api/setup/status`
