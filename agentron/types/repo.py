from typing import Protocol
from enum import IntEnum

from agentron.types.model import Model


class ModelRepoPriority(IntEnum):
    EXCLUSIVE = 100

    DEFAULT = 0


class ModelRepo(Protocol):
    def get_model(self, provider: str, model: str) -> Model: ...

    def get_priority(self, provider: str) -> ModelRepoPriority:
        """
        Repositories with higher priority will be searched first when looking up models.
        """
        ...
