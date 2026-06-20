"""Configuration management for ocom."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

APP_NAME = "ocom"


def get_config_dir() -> Path:
    """Get the config directory (Linux-style ~/.config/ocom on all platforms)."""
    return Path.home() / ".config" / APP_NAME


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "config.toml"


class GeneralConfig(BaseModel):
    """General application configuration."""

    refresh_interval: int = Field(
        default=2, ge=1, description="Status check interval in seconds"
    )
    auto_connect: bool = Field(
        default=False, description="Auto-connect to default OpenVPN config"
    )


class OpenVPNConfig(BaseModel):
    """OpenVPN-specific configuration."""

    enabled: bool = True
    config_dirs: list[str] = Field(default=["~/.openvpn", "~/vpn-configs"])
    default_config: str = ""


class SpoofDPIConfig(BaseModel):
    """SpoofDPI-specific configuration."""

    enabled: bool = True
    dns_addr: str = "8.8.8.8:53"
    dns_mode: Literal["udp", "https", "system"] = "https"
    port: int = Field(default=8080, ge=1, le=65535)
    system_proxy: bool = False


class WarpConfig(BaseModel):
    """Cloudflare WARP-specific configuration."""

    enabled: bool = True
    mode: Literal["warp", "doh", "proxy"] = "warp"


class TailscaleConfig(BaseModel):
    """Tailscale-specific configuration."""

    enabled: bool = True


class GoodbyeDPIConfig(BaseModel):
    """GoodbyeDPI-specific configuration (Windows only)."""

    enabled: bool = True
    mode: int = Field(default=9, ge=1, le=9, description="Preset mode (1-9)")
    block_quic: bool = Field(default=True, description="Block QUIC/HTTP3 protocol")


class AppConfig(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        toml_file=get_config_path(),
        extra="ignore",
    )

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    openvpn: OpenVPNConfig = Field(default_factory=OpenVPNConfig)
    spoofdpi: SpoofDPIConfig = Field(default_factory=SpoofDPIConfig)
    warp: WarpConfig = Field(default_factory=WarpConfig)
    tailscale: TailscaleConfig = Field(default_factory=TailscaleConfig)
    goodbyedpi: GoodbyeDPIConfig = Field(default_factory=GoodbyeDPIConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Configure settings sources.

        Values passed explicitly (``init_settings``) take priority so that
        ``load(path)`` can supply file contents directly; the default config at
        ``get_config_path()`` is used as a fallback when it exists.
        """
        toml_path = get_config_path()
        if toml_path.exists():
            return (
                init_settings,
                TomlConfigSettingsSource(settings_cls, toml_file=toml_path),
            )
        return (init_settings,)

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        """Load configuration from TOML file.

        Args:
            path: Path to config file. Uses default if None.

        Returns:
            Loaded AppConfig, or defaults if file doesn't exist.
        """
        if path and path.exists():
            return cls(**TomlConfigSettingsSource(cls, toml_file=path)())
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Save configuration to TOML file.

        Args:
            path: Path to config file. Uses default if None.
        """
        config_path = path or get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(self._to_toml())

    def _to_toml(self) -> str:
        """Convert config to TOML string."""
        sections: dict[str, dict[str, object]] = {
            "general": {
                "refresh_interval": self.general.refresh_interval,
                "auto_connect": self.general.auto_connect,
            },
            "openvpn": {
                "enabled": self.openvpn.enabled,
                "config_dirs": self.openvpn.config_dirs,
                "default_config": self.openvpn.default_config,
            },
            "spoofdpi": {
                "enabled": self.spoofdpi.enabled,
                "dns_addr": self.spoofdpi.dns_addr,
                "dns_mode": self.spoofdpi.dns_mode,
                "port": self.spoofdpi.port,
                "system_proxy": self.spoofdpi.system_proxy,
            },
            "warp": {
                "enabled": self.warp.enabled,
                "mode": self.warp.mode,
            },
            "tailscale": {
                "enabled": self.tailscale.enabled,
            },
            "goodbyedpi": {
                "enabled": self.goodbyedpi.enabled,
                "mode": self.goodbyedpi.mode,
                "block_quic": self.goodbyedpi.block_quic,
            },
        }
        lines = []
        for section, values in sections.items():
            lines.append(f"[{section}]")
            for key, value in values.items():
                lines.append(f"{key} = {self._format_toml_value(value)}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_toml_value(value: object) -> str:
        """Format a value for TOML output."""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, int):
            return str(value)
        if isinstance(value, list):
            return repr(value)
        return f'"{value}"'
