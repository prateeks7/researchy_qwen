import threading

_local = threading.local()


def set_model(model: str) -> None:
    _local.model = model


def get_model() -> str:
    return getattr(_local, 'model', '72b')
