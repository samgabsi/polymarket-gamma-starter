# Live CLOB SDK Mapping

Version: 1.0.0-real

This release activates the manual-live SDK mapping inside `app/live_clob_adapter.py` while preserving default-off operation.

## Runtime dependency

Install the optional dependency only in an operator-controlled live runtime:

```bash
pip install -r requirements-live-optional.txt
```

`requirements-live-optional.txt` pins `py-clob-client==0.34.6` for the inspected mapping.

## Mapped SDK methods

The adapter maps:

- `py_clob_client.client.ClobClient`
- `py_clob_client.clob_types.ApiCreds`
- `py_clob_client.clob_types.OrderArgs`
- `py_clob_client.clob_types.OrderType`
- `py_clob_client.clob_types.OpenOrderParams`
- `py_clob_client.order_builder.constants.BUY` / `SELL`
- `client.create_order(order_args)`
- `client.post_order(signed_order, order_type)`
- `client.cancel(order_id)`
- `client.get_order(order_id)`
- `client.get_orders(OpenOrderParams())`

## Validation posture

Normal validation probes imports and method presence without constructing a signed order, touching a wallet, or calling the network. Real SDK calls happen only when a manual record action reaches `adapter_mode=real_live` after all gates pass.

## Operator responsibility

Before enabling real trading, review current Polymarket docs, confirm token allowances/funding, test with very small deliberate limits, and keep the kill switch active until the exact live window. Automated validation must not submit or cancel live orders.


## v1.1.0 operations note

SDK-backed manual submit/cancel code remains behind the adapter boundary and manual control plane. Normal verification and validation do not call real submit/cancel methods.
