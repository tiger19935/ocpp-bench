from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ocpp_bench.cli import app


def test_cli_help_lists_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "csms" in result.output
    assert "sim" in result.output


def test_sim_missing_scenario_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "sim",
            "--target",
            "ws://127.0.0.1:1/ocpp",
            "--scenario",
            str(tmp_path / "nope.yaml"),
            "--no-assert-csms",
        ],
    )
    assert result.exit_code != 0
    assert "scenario file not found" in result.output


def test_sim_rejects_non_mapping_scenario(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not a mapping\n")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "sim",
            "--target",
            "ws://127.0.0.1:1/ocpp",
            "--scenario",
            str(bad),
            "--no-assert-csms",
        ],
    )
    assert result.exit_code != 0
    assert "scenario YAML" in result.output
