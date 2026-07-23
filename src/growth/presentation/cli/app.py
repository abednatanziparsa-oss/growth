"""Growth OS command-line interface.

Thin presentation layer: translates user intent into use-case calls
and renders results. No business logic here. Today: a single
``--version`` flag (the bootstrap vertical slice). Roadmap phases add
real subcommands (``plan apply``, ``sync``, ``report``, etc.).

Why Typer: type-driven, minimal boilerplate, great help output, and
its CliRunner is trivially testable. The whole CLI depends only on
``growth.application`` (and ``growth.kernel`` for wiring), never on
``growth.infrastructure`` directly — import-linter enforces this.
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from growth import __version__
from growth.kernel.bootstrap import build_app

__all__ = ["app", "run", "version_callback"]


def version_callback(value: bool) -> None:
    """Print the installed version and exit when ``--version`` is passed.

    Args:
        value: Whether the ``--version`` flag was set.
    """

    if value:
        typer.echo(f"growth-os {__version__}")
        raise typer.Exit(code=0)


app = typer.Typer(
    name="growth",
    help="Growth OS — a personal growth operating system.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def main(
    version: Annotated[  # noqa: ARG001 — consumed by version_callback above
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = False,
) -> None:
    """Growth OS — a personal growth operating system.

    Planning, knowledge management, learning, review, and execution
    in one cohesive system.

    Run ``growth --help`` to see available subcommands (more arrive per
    roadmap phase; bootstrap ships only ``--version``).
    """

    # The callback body runs when no subcommand matches. We build the
    # App here as a smoke check — if Settings or Container wiring is
    # broken, the user sees it immediately rather than on first
    # subcommand use. Construction is cheap (Noop everywhere).
    build_app()


def run() -> None:
    """Console-script entry point (referenced from ``[project.scripts]``)."""

    # Typer's standalone mode handles SystemExit / Exit internally.
    app(standalone_mode=False)

    # If Typer did not exit on its own (e.g. callback ran without raising),
    # exit cleanly.
    sys.exit(0)
