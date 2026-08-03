"""Network tool implementations."""

from typing import TYPE_CHECKING

from ocom.core.process import IS_WINDOWS
from ocom.tools.openvpn import OpenVPNTool
from ocom.tools.spoofdpi import SpoofDPITool
from ocom.tools.tailscale import TailscaleTool
from ocom.tools.warp import WarpTool

if TYPE_CHECKING:
    from ocom.core.tool import BaseTool

# Conditionally import platform-specific tools
if IS_WINDOWS:
    from ocom.tools.goodbyedpi import GoodbyeDPITool

__all__ = ["OpenVPNTool", "SpoofDPITool", "TailscaleTool", "WarpTool", "get_all_tools"]
if IS_WINDOWS:
    __all__ += ["GoodbyeDPITool"]


def get_all_tools() -> list[BaseTool]:
    """Get instances of all available tools for the current platform.

    Returns:
        A list of tool instances suitable for the current platform.
    """
    tools: list[BaseTool] = [OpenVPNTool(), WarpTool(), TailscaleTool()]

    # Add platform-specific DPI bypass tool
    if IS_WINDOWS:
        tools.append(GoodbyeDPITool())
    else:
        tools.append(SpoofDPITool())

    return tools
