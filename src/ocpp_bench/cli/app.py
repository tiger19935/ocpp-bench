from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml

from ocpp_bench.config import Protocol, Settings
from ocpp_bench.csms import CsmsServer
from ocpp_bench.logging import configure
from ocpp_bench.sim import Report, RunOptions, run_scenario
from ocpp_bench.sim.scenarios import load_scenario

app = typer.Typer(add_completion=False, no_args_is_help=True, help="ocpp-bench")

SCENARIO_DIR = Path(__file__).resolve().parents[3] / "scenarios"


@app.command()
def csms(
    host: Annotated[str, typer.Option(help="Bind address")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="OCPP websocket port")] = 9000,
    admin_port: Annotated[int, typer.Option(help="Admin + /metrics port")] = 9100,
    protocol: Annotated[Protocol, typer.Option(help="OCPP version(s) to accept")] = Protocol.BOTH,
    log_json: Annotated[bool, typer.Option(help="Emit JSON logs")] = True,
) -> None:
    settings = Settings(
        host=host, port=port, admin_port=admin_port, protocol=protocol, log_json=log_json
    )
    configure(level=settings.log_level, json_output=settings.log_json)
    server = CsmsServer.from_settings(settings)
    asyncio.run(server.serve())


@app.command()
def sim(
    target: Annotated[str, typer.Option(help="ws://host:port/ocpp")],
    scenario: Annotated[str, typer.Option(help="Scenario name or path to YAML file")],
    stations: Annotated[int | None, typer.Option(help="Override station count")] = None,
    duration: Annotated[float | None, typer.Option(help="Override duration_sec")] = None,
    protocol: Annotated[str, typer.Option(help="OCPP subprotocol")] = "ocpp1.6",
    admin_url: Annotated[
        str | None,
        typer.Option(help="CSMS admin URL for assertions (e.g. http://host:9100)"),
    ] = None,
    no_assert_csms: Annotated[
        bool, typer.Option(help="Skip CSMS-side assertions via admin endpoint")
    ] = False,
    report_json: Annotated[Path | None, typer.Option(help="Write JSON report to this path")] = None,
) -> None:
    configure(level="info", json_output=False)
    data = _load_scenario_data(scenario)
    _apply_overrides(data, stations=stations, duration_sec=duration, protocol=protocol)
    scn = load_scenario(data)
    opts = RunOptions(target=target, admin_url=None if no_assert_csms else admin_url)
    report: Report = asyncio.run(run_scenario(scn, opts))
    typer.echo(report.to_table())
    if report_json is not None:
        report_json.write_text(report.to_json())
    sys.exit(0 if report.passed else 1)


def _load_scenario_data(scenario: str) -> dict[str, object]:
    path = Path(scenario)
    if not path.is_file():
        guess = SCENARIO_DIR / f"{scenario}.yaml"
        if guess.is_file():
            path = guess
        else:
            raise typer.BadParameter(f"scenario file not found: {scenario}")
    loaded = yaml.safe_load(path.read_text())
    if not isinstance(loaded, dict):
        raise typer.BadParameter(f"scenario YAML must be a mapping: {path}")
    return loaded


def _apply_overrides(
    data: dict[str, object],
    *,
    stations: int | None,
    duration_sec: float | None,
    protocol: str,
) -> None:
    if stations is not None and "stations" in data:
        data["stations"] = stations
    if stations is not None and data.get("type") == "flapping":
        data["stable_stations"] = stations
    if duration_sec is not None and "duration_sec" in data:
        data["duration_sec"] = duration_sec
    if protocol:
        data.setdefault("protocol", protocol)


if __name__ == "__main__":
    app()
