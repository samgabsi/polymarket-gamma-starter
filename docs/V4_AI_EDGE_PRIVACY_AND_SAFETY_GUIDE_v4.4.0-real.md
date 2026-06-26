# AI Edge Privacy and Safety Guide - v4.4.0-real

AI Edge Research inherits the console's fail-closed safety posture.

## Privacy Defaults

- Redaction before send is enabled.
- Raw prompts are not stored.
- Raw responses are not stored.
- Prompt hashes are logged instead of prompt bodies.
- Source URLs are allowed by default, but source URL storage can be disabled with `AI_EDGE_ALLOW_SOURCE_URLS=false`.
- Runtime/private data is not sent by default.
- Web search is disabled by default.

## Safety Boundary

AI Edge Research does not:

- place orders
- cancel orders
- approve trades
- sign transactions
- arm live trading
- disable the kill switch
- disable read-only mode
- bypass backend gates
- provide financial advice

Market-implied comparison is disabled by default because it can be misread as a trading edge. When enabled, it remains research-only and must be reviewed by a human.
