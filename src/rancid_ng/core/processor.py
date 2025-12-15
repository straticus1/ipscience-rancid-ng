"""
ProcessHistory - Core output processing and accumulation system.

This is a direct port of the Perl ProcessHistory() function from rancid.pm.
It accumulates output lines into tagged sections with optional sorting.

The original Perl interface:
    ProcessHistory(tag, sort_func, sort_key, output_string)

Python interface:
    processor = ProcessHistory(output_stream)
    processor.add(tag, sort_func, sort_key, output_string)
    processor.flush()
"""

from __future__ import annotations

import sys
from collections import defaultdict
from io import StringIO
from typing import Callable, TextIO

from rancid_ng.core.sorting import keysort, keynsort, numsort, valsort, ipsort


class ProcessHistory:
    """
    Accumulates and processes configuration output with sectioning and sorting.

    This class replicates the Perl ProcessHistory() function behavior:
    - Output lines can be tagged into sections
    - Sections can have custom sort functions
    - When the tag or sort function changes, accumulated output is flushed
    - Lines without tags are output immediately

    Example:
        >>> processor = ProcessHistory(sys.stdout)
        >>> processor.add("COMMENTS", "keysort", "A1", "!Chassis: 7200\\n")
        >>> processor.add("COMMENTS", "keysort", "B1", "!Memory: 256MB\\n")
        >>> processor.add("COMMENTS", "keysort", "A2", "!CPU: R7000\\n")
        >>> processor.flush()
        !Chassis: 7200
        !CPU: R7000
        !Memory: 256MB
    """

    # Map of sort function names to implementations
    SORT_FUNCTIONS: dict[str, Callable] = {
        "keysort": keysort,
        "keynsort": keynsort,
        "numsort": numsort,
        "valsort": valsort,
        "ipsort": ipsort,
    }

    def __init__(self, output: TextIO | None = None):
        """
        Initialize ProcessHistory.

        Args:
            output: Output stream (defaults to sys.stdout)
        """
        self.output = output or sys.stdout
        self._current_tag: str = ""
        self._current_command: str = ""
        self._history: dict[str, str] = {}
        self._history_order: list[str] = []  # Track insertion order for keynsort

    def add(
        self,
        tag: str = "",
        sort_func: str = "",
        sort_key: str = "",
        *strings: str,
    ) -> bool:
        """
        Add output to the history buffer with optional sectioning and sorting.

        This replicates the Perl ProcessHistory() behavior:
        - If tag or sort_func changes from previous call, flush accumulated output
        - If tag and sort_func are provided with sort_key, accumulate with key
        - If tag and sort_func are provided without sort_key, accumulate in order
        - If neither tag nor sort_func, output immediately

        Args:
            tag: Section tag (e.g., "COMMENTS", "CONFIG")
            sort_func: Sort function name ("keysort", "ipsort", etc.)
            sort_key: Sort key for this line (e.g., "A1", "B2")
            *strings: Output strings to process

        Returns:
            True on success
        """
        output_str = "".join(strings)

        # Check if we need to flush (tag or command changed)
        if ((tag != self._current_tag or sort_func != self._current_command)
                and self._history):
            self._flush_history()

        # Process based on what's provided
        if tag and sort_func and sort_key:
            # Accumulate with sort key
            if sort_key in self._history:
                self._history[sort_key] += output_str
            else:
                self._history[sort_key] = output_str
                self._history_order.append(sort_key)
        elif tag and sort_func:
            # Accumulate in insertion order (use auto-incrementing key)
            key = str(len(self._history_order))
            self._history[key] = output_str
            self._history_order.append(key)
        else:
            # No tag/sort_func - output immediately
            self.output.write(output_str)

        self._current_tag = tag
        self._current_command = sort_func

        return True

    def _flush_history(self) -> None:
        """Flush accumulated history using the current sort function."""
        if not self._history:
            return

        # Get the sort function
        sort_func = self.SORT_FUNCTIONS.get(self._current_command)

        if sort_func:
            # Apply sort function and output
            sorted_lines = sort_func(self._history)
            for line in sorted_lines:
                self.output.write(line)
        else:
            # No valid sort function - output in insertion order
            for key in self._history_order:
                self.output.write(self._history[key])

        # Clear history
        self._history.clear()
        self._history_order.clear()

    def flush(self) -> None:
        """Flush any remaining accumulated output."""
        self._flush_history()
        self._current_tag = ""
        self._current_command = ""

    def reset(self) -> None:
        """Reset the processor state completely."""
        self._history.clear()
        self._history_order.clear()
        self._current_tag = ""
        self._current_command = ""


# Global instance for compatibility with procedural code
_global_processor: ProcessHistory | None = None


def get_processor(output: TextIO | None = None) -> ProcessHistory:
    """Get or create the global ProcessHistory instance."""
    global _global_processor
    if _global_processor is None:
        _global_processor = ProcessHistory(output)
    return _global_processor


def set_processor(processor: ProcessHistory) -> None:
    """Set the global ProcessHistory instance."""
    global _global_processor
    _global_processor = processor


def process_history(
    tag: str = "",
    sort_func: str = "",
    sort_key: str = "",
    *strings: str,
) -> bool:
    """
    Functional interface to ProcessHistory for compatibility.

    This provides the same interface as the original Perl ProcessHistory().
    """
    return get_processor().add(tag, sort_func, sort_key, *strings)
