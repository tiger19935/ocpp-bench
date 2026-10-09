import typer

app = typer.Typer(add_completion=False, no_args_is_help=True, help="ocpp-bench")


@app.command()
def csms() -> None:
    raise typer.Exit(code=0)


@app.command()
def sim() -> None:
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
