"""Tests for AppConfig and related configuration classes."""

from pathlib import Path

from ocom.config import (
    AppConfig,
    GeneralConfig,
    GoodbyeDPIConfig,
    OpenVPNConfig,
    SpoofDPIConfig,
    TailscaleConfig,
    WarpConfig,
)


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
        """Loading from a missing TOML file should return an AppConfig without raising."""
        missing_path = tmp_path / "nonexistent.toml"
        config = AppConfig.load(missing_path)
        assert isinstance(config, AppConfig)
