# Failure modes

| Scenario                      | CSMS behaviour                                                                        | Test name                                                                 |
|-------------------------------|---------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| normal                        | Full charging session completes; latency within target                                | `tests/integration/test_sim_normal`                                       |
| soak                          | Steady heartbeats for M seconds; no drops                                             | `tests/integration/test_sim_scenarios::test_soak_scenario_runs_briefly`   |
| reconnect-storm               | All stations recover within recover_within_sec                                        | `tests/integration/test_sim_scenarios::test_reconnect_storm_recovers`     |
| flapping-charger              | One flapper is quarantined; stable stations' p95 does not degrade >20%                | `tests/integration/test_sim_scenarios::test_flapping_isolation`           |
| slow-consumer                 | Server-initiated call times out at `call_timeout_sec`; station marked Unresponsive    | `tests/integration/test_call_timeout`                                     |
| session recovery              | Reconnect resumes txn; late StopTransaction accepted and flagged                      | `tests/integration/test_session_recovery`                                 |
| duplicate StartTransaction    | Same transactionId returned within duplicate window                                   | `tests/integration/test_sim_scenarios::test_duplicate_start_same_id`      |
| out-of-order MeterValues      | Accepted as-is; audit retains original timestamps                                     | `tests/integration/test_sim_scenarios::test_out_of_order_metervalues`     |
| oversized MeterValues         | Single large payload accepted up to size_kb                                           | `tests/integration/test_sim_scenarios::test_oversized_metervalues`        |
| boot-loop                     | Repeated BootNotification does not crash; eventually triggers quarantine              | `tests/integration/test_sim_scenarios::test_boot_loop`                    |
| inbound queue overflow        | CALLERROR InboundQueueFull on the Call; drop counter increments                       | `tests/integration/test_backpressure`                                     |
| unknown subprotocol           | 400 rejection at WS handshake                                                         | `tests/integration/test_server_handshake::test_rejects_unknown_subprotocol`|
