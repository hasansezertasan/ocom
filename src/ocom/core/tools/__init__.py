"""Network tool implementations."""

from typing import TYPE_CHECKING

from ocom.core.process import IS_WINDOWS
from ocom.core.tools.goodbyedpi import GoodbyeDPITool
from ocom.core.tools.openvpn import OpenVPNTool
from ocom.core.tools.spoofdpi import SpoofDPITool
from ocom.core.tools.tailscale import TailscaleTool
from ocom.core.tools.warp import WarpTool

if TYPE_CHECKING:
    from ocom.core.tool import BaseTool

# GoodbyeDPITool is imported unconditionally — its module imports cleanly on
# every platform — and only instantiated on Windows (see get_all_tools).
__all__ = [
    "GoodbyeDPITool",
    "OpenVPNTool",
    "SpoofDPITool",
    "TailscaleTool",
    "WarpTool",
    "get_all_tools",
]


def get_all_tools() -> list[BaseTool]:
    """Get instances of all available tools for the current platform.

    Returns:
        A list of tool instances suitable for the current platform.
    """
    tools: list[BaseTool] = [OpenVPNTool(), WarpTool(), TailscaleTool()]
    # GoodbyeDPI (Windows) and SpoofDPI (Unix) are the mutually exclusive DPI
    # bypass tools; only one applies per platform.
    tools.append(GoodbyeDPITool() if IS_WINDOWS else SpoofDPITool())
    return tools
