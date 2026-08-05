"""Smoke tests for ocom package."""


def test_smoke() -> None:
    """Test that the package can be imported."""
    import ocom  # ruff: ignore[import-outside-top-level]

    assert ocom is not None
