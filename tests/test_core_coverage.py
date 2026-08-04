"""Targeted coverage for core branches not exercised by the main suites.

Covers the platform-specific ``is_admin`` paths, the ``start_process`` env-merge
branch, the ``stop_process`` already-reaped path, and the AppConfig source
selection when no config file exists on disk.
"""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import ocom.core.process as process_mod
from ocom.config import AppConfig
from ocom.core.process import ProcessManager, is_admin

if TYPE_CHECKING:
    import asyncio
    from pathlib import Path

    import pytest


class TestIsAdmin:
    """Cover both platform branches of is_admin()."""

    def test_non_windows_uses_getuid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On non-Windows, admin status comes from a zero uid."""
        monkeypatch.setattr(process_mod, "IS_WINDOWS", False)
        monkeypatch.setattr(process_mod.os, "getuid", lambda: 0, raising=False)
        assert is_admin() is True

        monkeypatch.setattr(process_mod.os, "getuid", lambda: 1000, raising=False)
        assert is_admin() is False

    def test_windows_admin_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows, a truthy IsUserAnAdmin() means elevated."""
        monkeypatch.setattr(process_mod, "IS_WINDOWS", True)
        fake_windll = SimpleNamespace(shell32=SimpleNamespace(IsUserAnAdmin=lambda: 1))
        monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)
        assert is_admin() is True

    def test_windows_probe_failure_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing ctypes probe is treated as not-admin."""
        monkeypatch.setattr(process_mod, "IS_WINDOWS", True)

        def _boom() -> int:
            msg = "no windll here"
            raise OSError(msg)

        fake_windll = SimpleNamespace(shell32=SimpleNamespace(IsUserAnAdmin=_boom))
        monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)
        assert is_admin() is False


class TestStartProcessEnv:
    """Cover the environment-merge branch of start_process."""

    async def test_env_is_merged(self) -> None:
        """A non-empty env is merged into the child environment."""
        proc = await ProcessManager.start_process(
            [sys.executable, "-c", "pass"], env={"OCOM_TEST_VAR": "1"}
        )
        try:
            await proc.wait()
        finally:
            if proc.returncode is None:  # pragma: no cover - defensive cleanup
                proc.kill()
                await proc.wait()
        assert proc.returncode == 0


class TestStopProcessAlreadyReaped:
    """Cover the ProcessLookupError branch of stop_process."""

    async def test_lookup_error_is_treated_as_stopped(self) -> None:
        """If terminate() races with reaping, stop_process reports success."""

        class _FakeProc:
            returncode: int | None = None

            def terminate(self) -> None:
                raise ProcessLookupError

        proc = cast("asyncio.subprocess.Process", _FakeProc())
        result = await ProcessManager.stop_process(proc)
        assert result is True


class TestAppConfigNoFile:
    """Cover the source-selection branch when no config file exists."""

    def test_defaults_when_config_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With no config file, only the init source is used and defaults hold."""
        missing = tmp_path / "absent" / "config.toml"
        monkeypatch.setattr("ocom.config.get_config_path", lambda: missing)
        config = AppConfig()
        assert config.general.refresh_interval == 2
