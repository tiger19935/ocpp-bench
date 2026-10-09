# Running the simulator against a third-party CSMS

The simulator in `ocpp-bench sim` is deliberately decoupled from this
repo's CSMS. Point it at any OCPP 1.6J central system that accepts the
`ocpp1.6` subprotocol on a path of the form `/ocpp/<charge_point_id>` and
it will drive scenarios the same way.

## Minimum setup

```
ocpp-bench sim \
  --target wss://your-csms.example.com/ocpp \
  --scenario normal \
  --stations 50 \
  --protocol ocpp1.6 \
  --no-assert-csms
```

`--no-assert-csms` skips the admin-endpoint checks (`/stations`,
quarantine counts). Scenarios still report pass/fail based on what the
simulator itself observed on the client side.

## Scenario fit

- `normal`, `soak`, `boot-loop`, `duplicate-start`,
  `out-of-order-metervalues`, `oversized-metervalues` work out of the
  box against any correct CSMS.
- `reconnect-storm` and `flapping-charger` work, but the assertion that
  the CSMS *quarantined* a flapping station is skipped under
  `--no-assert-csms`; you can still observe the p95 isolation delta.
- `slow-consumer` requires the server to actually issue
  RemoteStartTransaction; without ours, drive that from your platform
  during the run.

## Reporting

Pass `--report-json path.json` to write a JSON report. The exit code is
`0` only when every assertion in the scenario passes.
