"""Tests for RANCID-NG ProcessHistory class."""

from io import StringIO

import pytest

from rancid_ng.core.processor import (
    ProcessHistory,
    get_processor,
    set_processor,
    process_history,
)


class TestProcessHistory:
    """Tests for ProcessHistory class."""

    def test_basic_output(self):
        """Test basic output without tags."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("", "", "", "line 1\n")
        processor.add("", "", "", "line 2\n")

        assert output.getvalue() == "line 1\nline 2\n"

    def test_tagged_sections_keysort(self):
        """Test tagged sections with keysort."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("COMMENTS", "keysort", "B", "!Comment B\n")
        processor.add("COMMENTS", "keysort", "A", "!Comment A\n")
        processor.add("COMMENTS", "keysort", "C", "!Comment C\n")
        processor.flush()

        assert output.getvalue() == "!Comment A\n!Comment B\n!Comment C\n"

    def test_tagged_sections_ipsort(self):
        """Test tagged sections with ipsort."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("ACL", "ipsort", "192.168.1.1", "permit 192.168.1.1\n")
        processor.add("ACL", "ipsort", "10.0.0.1", "permit 10.0.0.1\n")
        processor.add("ACL", "ipsort", "172.16.0.1", "permit 172.16.0.1\n")
        processor.flush()

        # Should sort by IP address
        result = output.getvalue()
        assert result.index("10.0.0.1") < result.index("172.16.0.1")
        assert result.index("172.16.0.1") < result.index("192.168.1.1")

    def test_section_change_triggers_flush(self):
        """Test that changing sections triggers flush of previous section."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("SECTION1", "keysort", "B", "line B\n")
        processor.add("SECTION1", "keysort", "A", "line A\n")
        # Changing section should flush SECTION1
        processor.add("SECTION2", "keysort", "X", "line X\n")

        # SECTION1 should have been flushed (sorted)
        result = output.getvalue()
        assert "line A\nline B\n" in result

        processor.flush()

    def test_tag_change_triggers_flush(self):
        """Test that changing tags triggers flush."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("TAG1", "keysort", "2", "line 2\n")
        processor.add("TAG1", "keysort", "1", "line 1\n")
        # Changing tag should flush
        processor.add("TAG2", "keysort", "A", "line A\n")
        processor.flush()

        result = output.getvalue()
        # First section should be sorted
        assert result.index("line 1") < result.index("line 2")

    def test_multiple_strings(self):
        """Test passing multiple strings."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("", "", "", "part1 ", "part2 ", "part3\n")

        assert output.getvalue() == "part1 part2 part3\n"

    def test_accumulate_same_key(self):
        """Test accumulating to same key."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("SEC", "keysort", "A", "line A part 1\n")
        processor.add("SEC", "keysort", "A", "line A part 2\n")
        processor.flush()

        assert output.getvalue() == "line A part 1\nline A part 2\n"

    def test_no_sort_func_uses_insertion_order(self):
        """Test that missing sort func uses insertion order."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("TAG", "unknown_sort", "", "line 1\n")
        processor.add("TAG", "unknown_sort", "", "line 2\n")
        processor.add("TAG", "unknown_sort", "", "line 3\n")
        processor.flush()

        assert output.getvalue() == "line 1\nline 2\nline 3\n"

    def test_reset(self):
        """Test reset clears state."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("TAG", "keysort", "A", "line A\n")
        processor.reset()
        processor.flush()

        # Should be empty after reset
        assert output.getvalue() == ""

    def test_keynsort(self):
        """Test numeric sorting."""
        output = StringIO()
        processor = ProcessHistory(output)

        processor.add("CONFIG", "keynsort", "10", "interface 10\n")
        processor.add("CONFIG", "keynsort", "2", "interface 2\n")
        processor.add("CONFIG", "keynsort", "1", "interface 1\n")
        processor.flush()

        result = output.getvalue()
        assert result.index("interface 1") < result.index("interface 2")
        assert result.index("interface 2") < result.index("interface 10")


class TestGlobalProcessor:
    """Tests for global processor functions."""

    def test_get_processor_creates_singleton(self):
        """Test that get_processor creates a singleton."""
        processor1 = get_processor()
        processor2 = get_processor()
        assert processor1 is processor2

    def test_set_processor(self):
        """Test setting custom processor."""
        output = StringIO()
        custom = ProcessHistory(output)
        set_processor(custom)

        # Should use our custom processor
        process_history("", "", "", "test line\n")
        assert output.getvalue() == "test line\n"

    def test_process_history_function(self):
        """Test functional interface."""
        output = StringIO()
        processor = ProcessHistory(output)
        set_processor(processor)

        result = process_history("TAG", "keysort", "A", "line A\n")
        assert result is True

        processor.flush()
        assert "line A\n" in output.getvalue()
