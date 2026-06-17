THRESHOLD = 10


def suppress(count: int) -> int | str:
    """Single function all count-returning endpoints must go through (EHDS Article 50)."""
    return "<10" if count < THRESHOLD else count
