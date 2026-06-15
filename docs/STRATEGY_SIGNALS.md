# Strategy Signals

Strategy signals are deterministic local records containing strategy, market, token, side, price, size, confidence, rationale, bindings, validation blockers, and hash. The autonomous engine consumes these records only; it does not invent trades from general text.

## Safety notes

- Live trading is dangerous and disabled by default.
- Autonomous trading is disabled by default.
- Automated tests must not submit or cancel real orders.
- Fake adapter receipts are local simulations, not exchange acknowledgements.
- Market-data and execution-quality estimates are not fill guarantees.
- This software is not financial advice.
- Do not commit `.env`, API keys, wallet keys, CLOB credentials, generated ledgers, or local state.
