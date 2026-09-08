from typing import Any, Dict
from backend.experiments.config_registry import ConfigRegistry


class DefaultBaseline:
    """Provides the frozen baseline configuration representing current production settings."""

    def __init__(self, registry: ConfigRegistry):
        self.registry = registry

    def select_next(self) -> Dict[str, Any]:
        return self.registry.get_defaults()
