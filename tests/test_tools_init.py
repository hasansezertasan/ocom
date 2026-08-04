"""Tests for the ocom.tools.get_all_tools factory."""

from typing import TYPE_CHECKING

from ocom.tools import (
    GoodbyeDPITool,
    OpenVPNTool,
    SpoofDPITool,
    TailscaleTool,
    WarpTool,
    get_all_tools,
)

if TYPE_CHECKING:
    import pytest


class TestGetAllTools:
    """Test the platform-aware tool registry factory."""

    def test_unix_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On non-Windows the DPI slot is filled by SpoofDPI."""
        monkeypatch.setattr("ocom.tools.IS_WINDOWS", False)
        tools = get_all_tools()
        types = [type(t) for t in tools]
        assert types == [OpenVPNTool, WarpTool, TailscaleTool, SpoofDPITool]

    def test_windows_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows the DPI slot is filled by GoodbyeDPI."""
        monkeypatch.setattr("ocom.tools.IS_WINDOWS", True)
        tools = get_all_tools()
        types = [type(t) for t in tools]
        assert types == [OpenVPNTool, WarpTool, TailscaleTool, GoodbyeDPITool]
