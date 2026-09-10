"""Errors that carry the failing stage and input location."""


class StageError(ValueError):
    def __init__(self, stage: str, message: str, source: str = "input") -> None:
        self.stage = stage
        self.source = source
        self.message = message
        super().__init__(f"{stage}: {source}: {message}")


class BoundaryOutputError(StageError):
    """An implementation produced a result outside its response contract."""


class ProviderError(StageError):
    """The explicitly selected extraction dependency failed."""
