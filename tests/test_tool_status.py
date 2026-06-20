"""Tests for ToolStatus enum."""

import pytest

from ocom.core.tool import ToolStatus


class TestToolStatusValues:
    """Test ToolStatus enum values."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected status values exist."""
        expected = {"unavailable", "stopped", "starting", "running", "stopping", "error"}
        actual = {status.value for status in ToolStatus}
        assert actual == expected

    def test_status_values_are_lowercase(self) -> None:
        """Status values should be lowercase for display."""
        for status in ToolStatus:
            assert status.value == status.value.lower()


class TestIsTransitioning:
    """Test the is_transitioning property."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            (ToolStatus.STARTING, True),
            (ToolStatus.STOPPING, True),
            (ToolStatus.UNAVAILABLE, False),
            (ToolStatus.STOPPED, False),
            (ToolStatus.RUNNING, False),
            (ToolStatus.ERROR, False),
        ],
    )
    def test_is_transitioning(self, status: ToolStatus, expected: bool) -> None:
        """Only STARTING and STOPPING are transitional states."""
        assert status.is_transitioning is expected


class TestCanStart:
    """Test the can_start property."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            (ToolStatus.STOPPED, True),
            (ToolStatus.ERROR, True),
            (ToolStatus.UNAVAILABLE, False),
            (ToolStatus.STARTING, False),
            (ToolStatus.RUNNING, False),
            (ToolStatus.STOPPING, False),
        ],
    )
    def test_can_start(self, status: ToolStatus, expected: bool) -> None:
        """Only STOPPED and ERROR states allow starting."""
        assert status.can_start is expected


class TestCanStop:
    """Test the can_stop property."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            (ToolStatus.RUNNING, True),
            (ToolStatus.UNAVAILABLE, False),
            (ToolStatus.STOPPED, False),
            (ToolStatus.STARTING, False),
            (ToolStatus.STOPPING, False),
            (ToolStatus.ERROR, False),
        ],
    )
    def test_can_stop(self, status: ToolStatus, expected: bool) -> None:
        """Only RUNNING state allows stopping."""
        assert status.can_stop is expected
