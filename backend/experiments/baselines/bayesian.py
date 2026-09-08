from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from backend.experiments.baselines.random import RandomSearchBaseline
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import TrialResult


class BayesianAdaptiveBaseline:
    """Surrogate-guided adaptive optimization using Gaussian Process regression and Upper Confidence Bound (UCB)."""

    def __init__(self, registry: ConfigRegistry, seed: int = 42):
        self.registry = registry
        self.random_sampler = RandomSearchBaseline(registry, seed=seed)
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def _encode_params(self, params: Dict[str, Any]) -> List[float]:
        """Convert parameter dictionary into numerical feature vector."""
        vec = [
            float(params.get("top_k", 5)),
            float(params.get("hybrid_search_alpha", 0.5)),
            float(params.get("rerank_threshold", 0.0)),
            float(params.get("routing_confidence_threshold", 0.6)),
            float(params.get("healing_max_retries", 2)),
        ]
        # One-hot encode chunk_variant
        variant = params.get("chunk_variant", "c700_o100")
        vec.extend([
            1.0 if variant == "c500_o50" else 0.0,
            1.0 if variant == "c700_o100" else 0.0,
            1.0 if variant == "c1500_o300" else 0.0,
        ])
        return vec

    def select_next(self, trial_history: List[TrialResult]) -> Dict[str, Any]:
        """Select next configuration maximizing UCB acquisition function over GP surrogate."""
        valid_trials = [t for t in trial_history if t.status.value == "completed"]

        # Initial exploration phase: requires at least 3 trials to fit GP
        if len(valid_trials) < 3:
            return self.random_sampler.select_next()

        X = np.array([self._encode_params(t.parameters) for t in valid_trials])
        y = np.array([t.objective_score for t in valid_trials])

        try:
            # Fit GP with Matern 5/2 kernel
            kernel = Matern(length_scale=1.0, nu=2.5)
            gp = GaussianProcessRegressor(kernel=kernel, alpha=1e-3, random_state=self.seed)
            gp.fit(X, y)

            # Sample 50 candidate configurations from search space
            candidates = [self.random_sampler.select_next() for _ in range(50)]
            cand_X = np.array([self._encode_params(c) for c in candidates])

            # Predict mean and uncertainty std
            means, stds = gp.predict(cand_X, return_std=True)

            # UCB acquisition: mu + kappa * sigma (exploration parameter kappa = 1.96)
            ucb_scores = means + 1.96 * stds
            best_idx = int(np.argmax(ucb_scores))

            return candidates[best_idx]

        except Exception:
            # Fallback to random sampling if GP fitting fails numerically
            return self.random_sampler.select_next()
