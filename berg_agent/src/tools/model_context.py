import threading

_local = threading.local()


def set_model(model: str) -> None:
    _local.model = model


def get_model() -> str:
    return getattr(_local, 'model', '72b')


def set_hf_token(token: str | None) -> None:
    _local.hf_token = token


def get_hf_token() -> str | None:
    return getattr(_local, 'hf_token', None)


def set_gemini_token(token: str | None) -> None:
    _local.gemini_token = token


def get_gemini_token() -> str | None:
    return getattr(_local, 'gemini_token', None)


def set_together_token(token: str | None) -> None:
    _local.together_token = token


def get_together_token() -> str | None:
    return getattr(_local, 'together_token', None)


def apply_thread_context(
    model: str,
    hf_token: str | None = None,
    gemini_token: str | None = None,
) -> None:
    """
    Set ALL token thread-local values in one call. Use at the top of every
    worker-thread function so tools called by the agent can resolve tokens
    via thread-local without relying on env vars.

    Passing None explicitly *clears* any stale token from a prior request
    that may have been served by the same worker thread.
    """
    _local.model = model
    _local.hf_token = hf_token
    _local.gemini_token = gemini_token
