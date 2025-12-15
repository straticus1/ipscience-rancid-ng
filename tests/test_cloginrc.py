"""Tests for RANCID-NG cloginrc parser."""

import os
from pathlib import Path

import pytest

from rancid_ng.config.cloginrc import CloginrcParser, AuthConfig, load_cloginrc


class TestCloginrcParser:
    """Tests for CloginrcParser class."""

    def test_load_file(self, sample_cloginrc):
        """Test loading a cloginrc file."""
        parser = CloginrcParser()
        result = parser.load_file(sample_cloginrc)
        assert result is True

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading a nonexistent file."""
        parser = CloginrcParser()
        result = parser.load_file(temp_dir / "nonexistent")
        assert result is False

    def test_get_user(self, sample_cloginrc):
        """Test getting user from config."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router1.example.com")
        assert config.user == "admin"

    def test_get_password(self, sample_cloginrc):
        """Test getting password from config."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router1.example.com")
        assert config.password == "secret123"
        assert config.enable_password == "enable456"

    def test_get_method(self, sample_cloginrc):
        """Test getting connection method."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router1.example.com")
        assert config.methods == ["ssh"]

    def test_glob_matching(self, sample_cloginrc):
        """Test glob pattern matching."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        # router* should match router-test
        config = parser.get_auth("router-test")
        assert config.user == "admin"

    def test_noenable(self, sample_cloginrc):
        """Test noenable directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("switch1.example.com")
        assert config.noenable is True

    def test_autoenable(self, sample_cloginrc):
        """Test autoenable directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("firewall1.example.com")
        assert config.autoenable is True

    def test_timeout(self, sample_cloginrc):
        """Test timeout directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("slow-router.example.com")
        assert config.timeout == 120

    def test_cyphertype(self, sample_cloginrc):
        """Test cyphertype directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("secure-router.example.com")
        assert config.cyphertype == "aes256-ctr"

    def test_identity(self, sample_cloginrc):
        """Test identity directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router-secure1.example.com")
        assert config.identity == "/home/admin/.ssh/id_rsa"

    def test_enauser(self, sample_cloginrc):
        """Test enauser directive."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router-enable1.example.com")
        assert config.enauser == "enableuser"

    def test_default_prompts(self, sample_cloginrc):
        """Test default prompt patterns."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("somehost.example.com")
        assert config.user_prompt is not None
        assert config.pass_prompt is not None
        assert config.enable_prompt is not None

    def test_first_match_wins(self, temp_dir):
        """Test that first matching pattern wins."""
        cloginrc = temp_dir / ".cloginrc"
        cloginrc.write_text("""
add user router1.example.com specific_user
add user router* generic_user
""")
        parser = CloginrcParser()
        parser.load_file(cloginrc)

        config = parser.get_auth("router1.example.com")
        assert config.user == "specific_user"

    def test_multiple_methods(self, sample_cloginrc):
        """Test multiple connection methods."""
        parser = CloginrcParser()
        parser.load_file(sample_cloginrc)

        config = parser.get_auth("router2.example.com")
        assert config.methods == ["telnet", "ssh"]

    def test_env_expansion(self, temp_dir):
        """Test environment variable expansion."""
        os.environ["TEST_RANCID_USER"] = "envuser"
        cloginrc = temp_dir / ".cloginrc"
        cloginrc.write_text("""
add user * $env(TEST_RANCID_USER)
""")
        parser = CloginrcParser()
        parser.load_file(cloginrc)

        config = parser.get_auth("anyhost")
        assert config.user == "envuser"

        del os.environ["TEST_RANCID_USER"]

    def test_braces_quoting(self, temp_dir):
        """Test brace-quoted values."""
        cloginrc = temp_dir / ".cloginrc"
        cloginrc.write_text("""
add password router* {pass with spaces} {enable with spaces}
""")
        parser = CloginrcParser()
        parser.load_file(cloginrc)

        config = parser.get_auth("router1")
        assert config.password == "pass with spaces"
        assert config.enable_password == "enable with spaces"

    def test_comments_ignored(self, temp_dir):
        """Test that comments are ignored."""
        cloginrc = temp_dir / ".cloginrc"
        cloginrc.write_text("""
# This is a comment
add user router* admin
# Another comment
""")
        parser = CloginrcParser()
        parser.load_file(cloginrc)

        config = parser.get_auth("router1")
        assert config.user == "admin"


class TestAuthConfig:
    """Tests for AuthConfig dataclass."""

    def test_get_password_prefers_user_password(self):
        """Test that get_password prefers user_password."""
        config = AuthConfig(
            hostname="test",
            password="vty_pass",
            user_password="user_pass",
        )
        assert config.get_password() == "user_pass"

    def test_get_password_falls_back(self):
        """Test that get_password falls back to password."""
        config = AuthConfig(
            hostname="test",
            password="vty_pass",
        )
        assert config.get_password() == "vty_pass"

    def test_get_enable_password(self):
        """Test get_enable_password method."""
        config = AuthConfig(
            hostname="test",
            enable_password="enable_pass",
        )
        assert config.get_enable_password() == "enable_pass"

    def test_default_methods(self):
        """Test default connection methods."""
        config = AuthConfig(hostname="test")
        assert config.methods == ["ssh", "telnet"]
