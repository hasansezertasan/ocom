"""Tests for AppConfig and related configuration classes."""

from typing import TYPE_CHECKING

import pytest

from ocom.__metadata__ import PROJECT_NAME
from ocom.core.config import (
    AppConfig,
    GeneralConfig,
    GoodbyeDPIConfig,
    OpenVPNConfig,
    Settings,
    SpoofDPIConfig,
    TailscaleConfig,
    WarpConfig,
)
from ocom.core.dirs import ROOT_FOLDER_PATH

if TYPE_CHECKING:
    from pathlib import Path

# Mirror the prefix the implementation derives from the project name.
ENV_PREFIX = f"{PROJECT_NAME.upper().replace('-', '_')}_"


class TestGeneralConfig:
    """Test GeneralConfig model."""

    def test_default_values(self) -> None:
        """GeneralConfig should have sensible defaults."""
        config = GeneralConfig()
        assert config.refresh_interval == 2
        assert config.auto_connect is False

    def test_auto_connect_can_be_enabled(self) -> None:
        """auto_connect should be settable to True."""
        config = GeneralConfig(auto_connect=True)
        assert config.auto_connect is True


class TestOpenVPNConfig:
    """Test OpenVPNConfig model."""

    def test_default_values(self) -> None:
        """OpenVPNConfig should have sensible defaults."""
        config = OpenVPNConfig()
        assert config.enabled is True
        assert config.config_dirs == ["~/.openvpn", "~/vpn-configs"]
        assert config.default_config == ""

    def test_default_config_can_be_set(self) -> None:
        """default_config should accept a path."""
        config = OpenVPNConfig(default_config="~/.openvpn/server.ovpn")
        assert config.default_config == "~/.openvpn/server.ovpn"


class TestGoodbyeDPIConfig:
    """Test GoodbyeDPIConfig model."""

    def test_default_values(self) -> None:
        """GoodbyeDPIConfig should have sensible defaults."""
        config = GoodbyeDPIConfig()
        assert config.enabled is True
        assert config.mode == 9
        assert config.block_quic is True

    def test_mode_range(self) -> None:
        """Mode should accept values 1-9."""
        for mode in range(1, 10):
            config = GoodbyeDPIConfig(mode=mode)
            assert config.mode == mode


class TestSpoofDPIConfig:
    """Test SpoofDPIConfig model."""

    def test_default_values(self) -> None:
        """SpoofDPIConfig should have sensible defaults."""
        config = SpoofDPIConfig()
        assert config.enabled is True
        assert config.dns_addr == "8.8.8.8:53"
        assert config.dns_mode == "https"
        assert config.port == 8080
        assert config.system_proxy is False

    def test_all_dns_modes_accepted(self) -> None:
        """All Literal dns_mode values should be valid."""
        for mode in ("udp", "https", "system"):
            config = SpoofDPIConfig(dns_mode=mode)
            assert config.dns_mode == mode


class TestWarpConfig:
    """Test WarpConfig model."""

    def test_default_values(self) -> None:
        """WarpConfig should have sensible defaults."""
        config = WarpConfig()
        assert config.enabled is True
        assert config.mode == "warp"

    def test_all_modes_accepted(self) -> None:
        """All Literal mode values should be valid."""
        for mode in ("warp", "doh", "proxy"):
            config = WarpConfig(mode=mode)
            assert config.mode == mode


class TestTailscaleConfig:
    """Test TailscaleConfig model."""

    def test_default_values(self) -> None:
        """TailscaleConfig should have sensible defaults."""
        config = TailscaleConfig()
        assert config.enabled is True


class TestAppConfig:
    """Test AppConfig settings."""

    def test_default_app_config(self) -> None:
        """AppConfig should load with all defaults."""
        config = AppConfig()
        assert config.general.refresh_interval == 2
        assert config.general.auto_connect is False
        assert config.openvpn.enabled is True
        assert config.openvpn.default_config == ""
        assert config.spoofdpi.enabled is True
        assert config.warp.enabled is True
        assert config.goodbyedpi.enabled is True

    def test_to_toml_includes_auto_connect(self) -> None:
        """_to_toml should include auto_connect setting."""
        config = AppConfig()
        config.general.auto_connect = True
        toml_str = config._to_toml()
        assert "auto_connect = true" in toml_str

    def test_to_toml_includes_goodbyedpi(self) -> None:
        """_to_toml should include GoodbyeDPI settings."""
        config = AppConfig()
        toml_str = config._to_toml()
        assert "[goodbyedpi]" in toml_str
        assert "mode = 9" in toml_str
        assert "block_quic = true" in toml_str

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Saving to TOML and loading back should round-trip all sections."""
        config = AppConfig()
        config.general.refresh_interval = 5
        config.general.auto_connect = True
        config.spoofdpi.dns_mode = "udp"
        config.spoofdpi.port = 9090
        config.warp.mode = "proxy"
        config.goodbyedpi.mode = 3
        config.goodbyedpi.block_quic = False

        config_path = tmp_path / "config.toml"
        config.save(config_path)
        assert config_path.exists()

        loaded = AppConfig.load(config_path)
        assert loaded.general.refresh_interval == 5
        assert loaded.general.auto_connect is True
        assert loaded.spoofdpi.dns_mode == "udp"
        assert loaded.spoofdpi.port == 9090
        assert loaded.warp.mode == "proxy"
        assert loaded.goodbyedpi.mode == 3
        assert loaded.goodbyedpi.block_quic is False

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """Loading from a missing TOML file returns defaults without raising."""
        missing_path = tmp_path / "nonexistent.toml"
        config = AppConfig.load(missing_path)
        assert isinstance(config, AppConfig)


class TestSettings:
    """Environment-sourced ``Settings`` (distinct from the TOML AppConfig)."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings expose the documented defaults when no env vars are set."""
        for name in ("DEBUG", "LOG_LEVEL", "CONFIG_DIR"):
            monkeypatch.delenv(f"{ENV_PREFIX}{name}", raising=False)

        settings = Settings()

        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.config_dir == ROOT_FOLDER_PATH

    def test_log_level_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The log level is read from the prefixed environment variable."""
        monkeypatch.setenv(f"{ENV_PREFIX}LOG_LEVEL", "DEBUG")

        assert Settings().log_level == "DEBUG"

    def test_config_dir_env_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The config directory is read from the prefixed environment variable."""
        monkeypatch.setenv(f"{ENV_PREFIX}CONFIG_DIR", str(tmp_path))

        assert Settings().config_dir == tmp_path

    @pytest.mark.parametrize("value", ["1", "true", "YES", "on", "y"])
    def test_debug_truthy(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Recognized truthy strings enable debug mode (case-insensitively)."""
        monkeypatch.setenv(f"{ENV_PREFIX}DEBUG", value)

        assert Settings().debug is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_debug_falsy(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Recognized falsy strings disable debug mode."""
        monkeypatch.setenv(f"{ENV_PREFIX}DEBUG", value)

        assert Settings().debug is False
