"""Smoke tests for ocom package."""


def test_smoke() -> None:
    """Test that the package can be imported."""
    import ocom  # noqa: PLC0415

    assert ocom is not None
