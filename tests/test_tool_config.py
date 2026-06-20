"""Tests for ToolConfig dataclass."""

from ocom.core.tool import ToolConfig


class TestToolConfigDefaults:
    """Test ToolConfig default values."""

    def test_default_values(self) -> None:
        """ToolConfig should have sensible defaults."""
        config = ToolConfig()
        assert config.enabled is True
        assert config.config_file is None
        assert config.config_dirs == []
        assert config.extra_args == []
        assert config.options == {}

    def test_mutable_defaults_are_independent(self) -> None:
        """Each instance should have independent mutable fields."""
        config1 = ToolConfig()
        config2 = ToolConfig()

        config1.config_dirs.append("/path1")
        config1.extra_args.append("--arg1")
        config1.options["key"] = "value"

        # config2 should not be affected
        assert config2.config_dirs == []
        assert config2.extra_args == []
        assert config2.options == {}


class TestToolConfigCustomValues:
    """Test ToolConfig with custom values."""

    def test_all_fields_can_be_set(self) -> None:
        """All fields should be settable at construction."""
        config = ToolConfig(
            enabled=False,
            config_file="/etc/tool/config.conf",
            config_dirs=["/etc/tool", "/home/user/.config/tool"],
            extra_args=["--verbose", "--debug"],
            options={"timeout": 30, "retries": 3, "enabled": True},
        )

        assert config.enabled is False
        assert config.config_file == "/etc/tool/config.conf"
        assert config.config_dirs == ["/etc/tool", "/home/user/.config/tool"]
        assert config.extra_args == ["--verbose", "--debug"]
        assert config.options == {"timeout": 30, "retries": 3, "enabled": True}

    def test_options_support_mixed_types(self) -> None:
        """Options dict should support str, bool, and int values."""
        config = ToolConfig(
            options={
                "string_opt": "value",
                "bool_opt": True,
                "int_opt": 42,
            }
        )

        assert config.options["string_opt"] == "value"
        assert config.options["bool_opt"] is True
        assert config.options["int_opt"] == 42
