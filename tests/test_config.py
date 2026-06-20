"""Tests for AppConfig and related configuration classes."""

from ocom.config import AppConfig, GeneralConfig, GoodbyeDPIConfig, OpenVPNConfig


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
