from datetime import timedelta

_FIRST_RETRY = timedelta(minutes=1)
_LONGEST_RETRY = timedelta(hours=1)


def retry_delay(failed_attempts: int) -> timedelta:
    """Wait before the next try: 1, 2, 4, 8... minutes, capped at one hour."""
    if failed_attempts < 1:
        raise ValueError("failed_attempts must be at least 1")
    return min(_FIRST_RETRY * (1 << (failed_attempts - 1)), _LONGEST_RETRY)


def gives_up(failed_attempts: int, *, max_attempts: int) -> bool:
    return failed_attempts >= max_attempts
