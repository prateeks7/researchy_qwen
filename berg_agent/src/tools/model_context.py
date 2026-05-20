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
