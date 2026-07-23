"""Bootstrap smoke test — exercises the full vertical slice.

This is the "thin real wire": it proves Settings loads, logging configures,
the Container wires, and the CLI responds. Every subsequent phase adds
unit/integration/contract tests next to the code it exercises.

Tagged as both ``unit`` (it tests a single CLI flag) and ``integration``
(it goes through Typer to kernel.bootstrap). The integration marker is
the canonical one for the fixture; ``unit`` allows running it in a
fast smoke-check suite.
"""

from __future__ import annotations

from typer.testing import CliRunner

from growth.presentation.cli.app import app

runner = CliRunner()


def test_growth_version_output() -> None:
    """``growth --version`` prints the expected version string and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert "growth-os" in result.stdout
