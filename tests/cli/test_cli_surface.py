"""CLI surface tests — `--list-presets`, `themes`, `create-preset`.

These exercise the typer Click runner without going through subprocess. They
assert that registered presets are visible and that the scaffold writes the
expected files. They do NOT do a full `render` invocation — that's the
integration suite's job (which mocks DataAccess).
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prettyplateau.cli.main import app


runner = CliRunner()


def test_list_presets_includes_plan_presets() -> None:
    result = runner.invoke(app, ["list-presets"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    for plan_preset in (
        "age_rainbow",
        "use_mosaic",
        "wood_survivor",
        "risk_choropleth",
        "survivor_timeline",
    ):
        assert plan_preset in out, f"{plan_preset} missing from --list-presets"


def test_themes_command_includes_plan_themes() -> None:
    result = runner.invoke(app, ["themes"])
    assert result.exit_code == 0
    out = result.stdout
    for plan_theme in ("default", "print", "sakura", "summer_matsuri", "snow", "neon_night"):
        assert plan_theme in out


def test_create_preset_emits_runnable_skeleton(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["create-preset", "my-test-preset", "--dest", str(tmp_path), "--name", "My Test Preset"],
    )
    assert result.exit_code == 0, result.stdout
    base = tmp_path / "prettyplateau_preset_my_test_preset"
    assert (base / "pyproject.toml").exists()
    assert (base / "src" / "prettyplateau_preset_my_test_preset" / "my_test_preset.py").exists()
    assert (base / "tests" / "test_my_test_preset.py").exists()
