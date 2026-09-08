import itertools
from typing import Any, Dict, List, Optional
from backend.experiments.config_registry import ConfigRegistry


class GridSearchBaseline:
    """Evaluates candidate configurations in systematic cartesian grid sequence."""

    def __init__(self, registry: ConfigRegistry):
        self.registry = registry
        self._grid: List[Dict[str, Any]] = self._build_grid()
        self._cursor = 0

    def _build_grid(self) -> List[Dict[str, Any]]:
        # Key representative values across the space to keep grid tractable
        candidate_values = {
            "top_k": [3, 5, 8],
            "hybrid_search_alpha": [0.3, 0.5, 0.7],
            "rerank_threshold": [0.0, 0.3],
            "routing_confidence_threshold": [0.5, 0.7],
            "healing_max_retries": [1, 2],
            "chunk_variant": ["c500_o50", "c700_o100", "c1500_o300"],
        }

        keys = list(candidate_values.keys())
        combos = list(itertools.product(*[candidate_values[k] for k in keys]))

        grid = []
        for combo in combos:
            params = dict(zip(keys, combo))
            grid.append(self.registry.validate_and_clamp(params))
        return grid

    def select_next(self, trial_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self._grid:
            return self.registry.get_defaults()
        selected = self._grid[self._cursor % len(self._grid)]
        self._cursor += 1
        return selected
