# ChatGPT Connector Blueprint - v4.2.0-real

This release includes a blueprint for future ChatGPT Apps/MCP integration. It does not enable a public MCP server by default.

## Defaults

- `CHATGPT_CONNECTOR_BLUEPRINT_ENABLED=true`
- `CHATGPT_MCP_SERVER_ENABLED=false`
- `CHATGPT_MCP_REQUIRE_AUTH=true`
- `CHATGPT_MCP_READ_ONLY=true`
- `OPENAI_ENABLE_REMOTE_MCP=false`

## Allowed Read-Only Tool Concepts

- Get platform summary
- Get route inventory
- Get task summary
- Get workspace summary
- Get cockpit summary
- Get dataset summary
- Get freshness summary
- Get simulation summary
- Get analytics summary
- Get migration plan summary
- Draft task suggestions
- Draft review summaries

## Forbidden Tool Concepts

- Place order
- Cancel order
- Approve trade
- Sign transaction
- Arm live trading
- Disable kill switch
- Disable read-only mode
- Mutate live configuration
- Export secrets
- Fetch private keys
- Fetch API keys

Example blueprint stubs live under `examples/chatgpt_connector/`.

