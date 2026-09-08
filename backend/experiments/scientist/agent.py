import json
import re
from typing import List, Optional
import httpx
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.experiments.baselines.bayesian import BayesianAdaptiveBaseline
from backend.experiments.config_registry import ConfigRegistry
from backend.experiments.models import CandidateProposal, ObjectiveConfig, TrialResult
from backend.experiments.scientist.prompt import (
    build_proposal_prompt,
    build_scientist_system_prompt,
)

logger = get_logger(__name__)


class AutonomousScientist:
    """LLM-driven experiment designer using local Ollama with deterministic Bayesian fallback."""

    def __init__(
        self,
        registry: Optional[ConfigRegistry] = None,
        model_name: Optional[str] = None,
        ollama_host: Optional[str] = None,
    ):
        self.registry = registry or ConfigRegistry()
        self.model_name = model_name or settings.MODEL_NAME
        self.ollama_host = ollama_host or settings.OLLAMA_HOST
        self.bayesian_fallback = BayesianAdaptiveBaseline(self.registry)

    async def propose_candidate(
        self,
        objective: ObjectiveConfig,
        trial_history: List[TrialResult],
        best_trial: Optional[TrialResult] = None,
    ) -> CandidateProposal:
        """Query LLM to generate next hypothesis and candidate parameters, falling back if needed."""
        system_prompt = build_scientist_system_prompt()
        user_prompt = build_proposal_prompt(
            objective=objective,
            registry=self.registry,
            trials=trial_history,
            best_trial=best_trial,
        )

        for attempt in range(2):
            try:
                raw_response = await self._call_ollama(system_prompt, user_prompt)
                parsed_json = self._extract_json(raw_response)

                if parsed_json and "parameters" in parsed_json:
                    # Validate parameters against search space
                    clamped_params = self.registry.validate_and_clamp(parsed_json["parameters"])
                    proposal = CandidateProposal(
                        hypothesis=parsed_json.get("hypothesis", "Iterative parameter refinement"),
                        expected_outcome=parsed_json.get("expected_outcome", "Improve objective score"),
                        parameters=clamped_params,
                        justification=parsed_json.get("justification", "Hypothesis-driven parameter tuning"),
                    )
                    logger.info("Scientist generated valid candidate proposal", hypothesis=proposal.hypothesis)
                    return proposal

            except Exception as e:
                logger.warning("Scientist LLM proposal attempt failed", attempt=attempt + 1, error=str(e))

        # Fallback to Bayesian Adaptive search if Ollama fails or output is malformed
        logger.warning("Scientist falling back to Bayesian Adaptive Search")
        fallback_params = self.bayesian_fallback.select_next(trial_history)
        return CandidateProposal(
            hypothesis="Surrogate-guided Gaussian Process exploration (Scientist Fallback)",
            expected_outcome="Maximize acquisition function over empirical trial distribution",
            parameters=fallback_params,
            justification="Automated statistical surrogate suggestion following LLM proposal timeout or format error.",
        )

    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "top_p": 0.9,
            },
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    def _extract_json(self, text: str) -> Optional[dict]:
        text = text.strip()
        # Direct parse attempt
        try:
            return json.loads(text)
        except Exception:
            pass

        # Regex search for JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return None
