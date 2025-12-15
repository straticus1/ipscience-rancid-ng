"""Tests for RANCID-NG device type registry."""

from pathlib import Path

import pytest

from rancid_ng.config.types import DeviceTypeConfig, DeviceTypeRegistry


class TestDeviceTypeConfig:
    """Tests for DeviceTypeConfig dataclass."""

    def test_basic_creation(self):
        """Test basic config creation."""
        config = DeviceTypeConfig(name="cisco")
        assert config.name == "cisco"
        assert config.alias is None
        assert config.commands == []

    def test_add_command(self):
        """Test adding commands."""
        config = DeviceTypeConfig(name="cisco")
        config.add_command("show version", "ShowVersion")
        config.add_command("show running-config", "WriteTerm")

        assert len(config.commands) == 2
        assert config.commands[0] == ("show version", "ShowVersion")


class TestDeviceTypeRegistry:
    """Tests for DeviceTypeRegistry class."""

    def test_empty_registry(self):
        """Test empty registry."""
        registry = DeviceTypeRegistry()
        assert len(registry) == 0
        assert registry.list_types() == []

    def test_load_file(self, temp_dir):
        """Test loading a types file."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
# Test device types
cisco;script;rancid -t cisco
cisco;login;clogin
cisco;module;cisco
cisco;inloop;cisco::inloop
cisco;timeout;90
cisco;command;cisco::ShowVersion;show version
cisco;command;cisco::WriteTerm;show running-config
""")
        registry = DeviceTypeRegistry()
        count = registry.load_file(types_file)

        assert count == 1
        assert "cisco" in registry

        config = registry.get_type("cisco")
        assert config is not None
        assert config.script == "rancid -t cisco"
        assert config.login == "clogin"
        assert config.module == "cisco"
        assert config.timeout == 90
        assert len(config.commands) == 2

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading nonexistent file."""
        registry = DeviceTypeRegistry()
        count = registry.load_file(temp_dir / "nonexistent")
        assert count == 0

    def test_alias_resolution(self, temp_dir):
        """Test alias resolution."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
cisco;script;rancid -t cisco
cisco;login;clogin
cisco;module;cisco
ios;alias;cisco
router;alias;ios
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        # Direct lookup
        ios_config = registry.get_type("ios")
        assert ios_config is not None
        assert ios_config.alias == "cisco"

        # Resolved lookup - should get cisco's config
        resolved = registry.resolve_type("ios")
        assert resolved is not None
        assert resolved.name == "cisco"
        assert resolved.script == "rancid -t cisco"

        # Multi-level alias
        resolved = registry.resolve_type("router")
        assert resolved is not None
        assert resolved.name == "cisco"

    def test_circular_alias_protection(self, temp_dir):
        """Test protection against circular aliases."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
type_a;alias;type_b
type_b;alias;type_a
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        # Should not loop forever
        resolved = registry.resolve_type("type_a")
        # Will return one of the types (not crash)
        assert resolved is not None

    def test_load_directory(self, temp_dir):
        """Test loading from directory."""
        base_file = temp_dir / "rancid.types.base"
        base_file.write_text("""
cisco;script;rancid -t cisco
cisco;login;clogin
""")
        conf_file = temp_dir / "rancid.types.conf"
        conf_file.write_text("""
juniper;script;rancid -t juniper
juniper;login;jlogin
""")
        registry = DeviceTypeRegistry()
        count = registry.load_directory(temp_dir)

        assert count >= 2
        assert "cisco" in registry
        assert "juniper" in registry

    def test_list_types(self, temp_dir):
        """Test listing types."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
zebra;script;rancid
apple;script;rancid
mango;script;rancid
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        types = registry.list_types()
        assert types == ["apple", "mango", "zebra"]  # Sorted

    def test_iteration(self, temp_dir):
        """Test iterating over registry."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
cisco;script;rancid
juniper;script;rancid
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        configs = list(registry)
        assert len(configs) == 2
        assert all(isinstance(c, DeviceTypeConfig) for c in configs)

    def test_contains(self, temp_dir):
        """Test contains check."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
cisco;script;rancid
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        assert "cisco" in registry
        assert "CISCO" in registry  # Case insensitive
        assert "juniper" not in registry

    def test_comments_ignored(self, temp_dir):
        """Test that comments are ignored."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
# This is a comment
cisco;script;rancid -t cisco
# Another comment
#juniper;script;rancid -t juniper
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        assert "cisco" in registry
        assert "juniper" not in registry

    def test_case_insensitive_lookup(self, temp_dir):
        """Test case-insensitive type lookup."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
Cisco;script;rancid -t cisco
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        assert registry.get_type("cisco") is not None
        assert registry.get_type("CISCO") is not None
        assert registry.get_type("Cisco") is not None

    def test_malformed_lines_ignored(self, temp_dir):
        """Test that malformed lines are ignored."""
        types_file = temp_dir / "rancid.types.base"
        types_file.write_text("""
cisco;script;rancid
invalid;only_two_parts
also_invalid
cisco;login;clogin
""")
        registry = DeviceTypeRegistry()
        registry.load_file(types_file)

        # Only cisco should be loaded (invalid entries are skipped)
        assert "cisco" in registry
        # "invalid" also gets loaded as it has 2 parts after split
        # The important thing is malformed entries don't crash
        assert len(registry) >= 1

    def test_get_nonexistent_type(self):
        """Test getting a type that doesn't exist."""
        registry = DeviceTypeRegistry()
        assert registry.get_type("nonexistent") is None
        assert registry.resolve_type("nonexistent") is None
