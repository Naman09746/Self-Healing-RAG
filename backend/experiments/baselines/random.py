import random
from typing import Any, Dict, Optional
from backend.experiments.config_registry import ConfigRegistry


class RandomSearchBaseline:
    """Samples valid configurations uniformly at random across parameter bounds."""

    def __init__(self, registry: ConfigRegistry, seed: Optional[int] = 42):
        self.registry = registry
        self.rng = random.Random(seed)

    def select_next(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for name, spec in self.registry.schema.items():
            param_type = spec.get("type")
            if param_type == "int":
                min_v = spec.get("min", 1)
                max_v = spec.get("max", 10)
                step = spec.get("step", 1)
                choices = list(range(min_v, max_v + 1, step))
                params[name] = self.rng.choice(choices)
            elif param_type == "float":
                min_v = spec.get("min", 0.0)
                max_v = spec.get("max", 1.0)
                step = spec.get("step", 0.05)
                steps = int(round((max_v - min_v) / step))
                choice_idx = self.rng.randint(0, steps)
                val = round(min_v + choice_idx * step, 2)
                params[name] = val
            elif param_type == "categorical":
                options = spec.get("options", [])
                params[name] = self.rng.choice(options) if options else spec.get("default")
        return self.registry.validate_and_clamp(params)
