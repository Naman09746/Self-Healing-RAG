"""Evaluation Agent — Offline RAGAS-based evaluation of pipeline outputs.

Uses RAGAS metrics to compute:
    - Faithfulness
    - Answer Relevancy
    - Context Precision
    - Context Recall (where ground truth permits)

Call ``run_offline_evaluation()`` after the pipeline has produced results
for a batch of queries. Results are returned as a dict of metric scores.

Heuristic fallback is preserved as ``FastRegressionEvaluator`` for cheap
local regression testing (zero API cost). Use ``RAGASEvaluator`` for
semantic LLM-based evaluation via OpenRouter/OpenAI.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvalSample:
    """A single evaluation sample."""
    query: str
    expected_answer: str
    contexts: list[str]
    actual_answer: str = ""
    retrieved_contexts: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating one or more samples."""
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    run_id: str = ""
    num_samples: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers — resolve evaluation LLM config from llm_config + settings
# ---------------------------------------------------------------------------

def _resolve_eval_config(llm_config: Optional[dict]) -> dict[str, str]:
    """Merge explicit llm_config with settings for evaluation.

    Priority: llm_config[model/base_url/api_key] > settings.EVALUATION_* > settings.OPENAI_* / gpt-4o-mini

    Note: application MODEL_NAME (e.g. nvidia/nemotron-3-ultra-550b:free) is NOT suitable
    for RAGAS which expects OpenAI-compatible JSON mode. Prefer EVALUATION_LLM or
    openai/gpt-4o-mini via OpenRouter.
    """
    cfg = llm_config or {}
    try:
        from backend.core.config import settings
    except Exception:
        return {
            "api_key": str(cfg.get("api_key", "")),
            "base_url": str(cfg.get("base_url", "")),
            "model": str(cfg.get("model", "") or "openai/gpt-4o-mini"),
            "embedding_model": str(cfg.get("embedding_model", "")),
        }
    api_key = cfg.get("api_key") or getattr(settings, "OPENAI_API_KEY", "") or ""
    base_url = (
        cfg.get("base_url")
        or getattr(settings, "EVALUATION_BASE_URL", "")
        or getattr(settings, "OPENAI_BASE_URL", "")
        or ""
    )
    # Prefer explicit evaluation model, else gpt-4o-mini (OpenRouter: openai/gpt-4o-mini)
    # Do NOT fallback to MODEL_NAME nemotron which fails ragas JSON mode
    eval_llm = getattr(settings, "EVALUATION_LLM", "") or ""
    if cfg.get("model"):
        model = str(cfg["model"])
    elif eval_llm:
        model = str(eval_llm)
    elif base_url and "openrouter.ai" in base_url:
        model = "openai/gpt-4o-mini"
    else:
        model = "gpt-4o-mini"
    embedding_model = (
        cfg.get("embedding_model")
        or getattr(settings, "EVALUATION_EMBEDDING_MODEL", "")
        or getattr(settings, "EMBEDDING_MODEL", "")
        or ""
    )
    # Normalize OpenRouter prefix requirement
    if base_url and "openrouter.ai" in base_url.lower() and model in ("gpt-4o-mini",):
        # Keep as is — OpenRouter proxies openai/*; user should set explicit model if needed
        pass
    return {
        "api_key": str(api_key),
        "base_url": str(base_url),
        "model": str(model),
        "embedding_model": str(embedding_model),
    }


# ---------------------------------------------------------------------------
# RAGAS evaluator (with graceful fallback)
# ---------------------------------------------------------------------------

class RAGASEvaluator:
    """Thin wrapper around RAGAS metrics with OpenRouter support.

    Supports OpenRouter via ``OPENAI_BASE_URL`` / ``EVALUATION_BASE_URL``
    and configurable ``EVALUATION_LLM``. Falls back to heuristic token-overlap
    when RAGAS is unavailable or LLM call fails.

    Metrics:
      - faithfulness
      - answer_relevancy
      - context_precision
      - context_recall (where ground truth available)
    """

    def __init__(self, llm_config: Optional[dict] = None) -> None:
        self._llm_config = llm_config or {}
        self._ragas_loaded: Optional[bool] = None
        self._evaluate = None
        self._faithfulness = None
        self._answer_relevancy = None
        self._context_precision = None
        self._context_recall = None

    def _ensure_ragas_loaded(self) -> bool:
        if self._ragas_loaded is not None:
            return self._ragas_loaded

        try:
            from ragas import evaluate

            # Prefer deprecated shim (provides pre-instantiated metric objects with llm=None)
            # which works with ragas 0.4.3 evaluate() auto-injection. Fallback to new collections.
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    from ragas.metrics import (
                        faithfulness,
                        answer_relevancy,
                        context_precision,
                        context_recall,
                    )
            except ImportError:
                # New collections path — modules, need class instances
                try:
                    from ragas.metrics import faithfulness, answer_relevancy, context_precision  # type: ignore

                    try:
                        from ragas.metrics import context_recall  # type: ignore
                    except ImportError:
                        from ragas.metrics.collections.context_recall import ContextRecall as _CR  # type: ignore

                        # Old instance path failed for recall, create placeholder
                        context_recall = _CR  # type: ignore
                except ImportError:
                    # Last resort: try collections classes (require llm — will be handled in evaluate)
                    from ragas.metrics.collections.faithfulness import Faithfulness as _F  # type: ignore
                    from ragas.metrics.collections.answer_relevancy import AnswerRelevancy as _AR  # type: ignore
                    from ragas.metrics.collections.context_precision import ContextPrecision as _CP  # type: ignore
                    from ragas.metrics.collections.context_recall import ContextRecall as _CR  # type: ignore

                    # Store classes; will instantiate with llm in _evaluate_with_ragas
                    faithfulness = _F  # type: ignore
                    answer_relevancy = _AR  # type: ignore
                    context_precision = _CP  # type: ignore
                    context_recall = _CR  # type: ignore

            resolved = _resolve_eval_config(self._llm_config)
            api_key = resolved.get("api_key", "")
            base_url = resolved.get("base_url", "")
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            if base_url:
                os.environ["OPENAI_BASE_URL"] = base_url

            # Quick smoke-test: datasets is required by RAGAS
            import datasets  # noqa: F401

            self._evaluate = evaluate
            self._faithfulness = faithfulness
            self._answer_relevancy = answer_relevancy
            self._context_precision = context_precision
            self._context_recall = context_recall
            self._ragas_loaded = True
            logger.info(
                "RAGAS evaluation backend is available (model=%s, base_url=%s, recall=%s).",
                resolved.get("model", ""),
                base_url or "(default)",
                bool(context_recall),
            )

        except ImportError as exc:
            logger.warning(
                "RAGAS or datasets not installed (%s). "
                "Falling back to heuristic scoring.",
                exc,
            )
            self._ragas_loaded = False
        except Exception as exc:
            logger.warning(
                "RAGAS initialisation failed (%s). "
                "Falling back to heuristic scoring.",
                exc,
            )
            self._ragas_loaded = False

        return self._ragas_loaded

    @property
    def _ragas_available(self) -> bool:
        return self._ensure_ragas_loaded()

    @_ragas_available.setter
    def _ragas_available(self, val: bool) -> None:
        self._ragas_loaded = val

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_samples(self, samples: list[EvalSample], force_heuristic: bool = False) -> EvalResult:
        """Evaluate a list of ``EvalSample`` objects.

        Returns an ``EvalResult`` with mean scores across all samples.
        """
        if not samples:
            return EvalResult(error="No samples provided.")

        t0 = time.monotonic()
        run_id = f"eval_{int(t0)}"

        if self._ragas_available and not force_heuristic:
            result = self._evaluate_with_ragas(samples)
        else:
            result = self._evaluate_heuristic(samples)

        result.run_id = run_id
        result.num_samples = len(samples)
        result.duration_seconds = time.monotonic() - t0

        logger.info(
            "Evaluation %s complete: "
            "faithfulness=%.3f, answer_relevancy=%.3f, context_precision=%.3f, context_recall=%.3f "
            "(%d samples in %.2f s%s)",
            run_id,
            result.faithfulness,
            result.answer_relevancy,
            result.context_precision,
            result.context_recall,
            result.num_samples,
            result.duration_seconds,
            f" error={result.error}" if result.error else "",
        )

        return result

    # ------------------------------------------------------------------
    # RAGAS path — explicit LLM/embeddings for OpenRouter support
    # ------------------------------------------------------------------

    def _evaluate_with_ragas(self, samples: list[EvalSample]) -> EvalResult:
        """Evaluate using the real RAGAS library with configurable LLM."""
        try:
            from datasets import Dataset

            data = {
                "question": [s.query for s in samples],
                "answer": [s.actual_answer for s in samples],
                "contexts": [s.retrieved_contexts or s.contexts for s in samples],
                "ground_truth": [s.expected_answer for s in samples],
            }

            dataset = Dataset.from_dict(data)

            resolved = _resolve_eval_config(self._llm_config)
            model = resolved.get("model", "gpt-4o-mini")
            base_url = resolved.get("base_url", "")
            api_key = resolved.get("api_key", "")

            # Build explicit llm / embeddings for ragas if possible (enables OpenRouter)
            llm = None
            embeddings = None
            try:
                # Try ragas llm factory (newer) — create OpenAI-compatible client first
                from openai import OpenAI

                client_kwargs: dict[str, Any] = {}
                if api_key:
                    client_kwargs["api_key"] = api_key
                if base_url:
                    client_kwargs["base_url"] = base_url
                # Only create client if we have a key; otherwise let ragas infer from env
                oai_client = OpenAI(**client_kwargs) if client_kwargs else None
                if oai_client is not None:
                    try:
                        from ragas.llms import llm_factory

                        llm = llm_factory(model, client=oai_client)  # type: ignore[arg-type]
                    except Exception as le:
                        logger.debug("llm_factory failed (%s), using env OpenAI client fallback.", le)
                        llm = None
                    try:
                        from ragas.embeddings import embedding_factory  # type: ignore

                        # Use OpenAI embeddings via same client; ragas infers from llm if None
                        embeddings = embedding_factory("openai", client=oai_client)  # type: ignore
                    except Exception as ee:
                        logger.debug("embedding_factory failed (%s), using ragas default.", ee)
                        embeddings = None
            except Exception as e:
                logger.debug("OpenAI client setup for RAGAS failed (%s), using defaults.", e)

            # Do not pass embeddings explicitly — ragas 0.4.3 OpenAIEmbeddings has
            # embed_query mismatch when using OpenRouter; let ragas infer from llm
            # and handle nan via heuristic fallback per metric
            metrics = [m for m in [self._faithfulness, self._answer_relevancy, self._context_precision, self._context_recall] if m is not None]
            # If metrics are classes (new collections), instantiate with llm
            instantiated: list[Any] = []
            for m in metrics:
                try:
                    # Old shim: already instance with .name
                    if hasattr(m, "name") or hasattr(m, "_required_columns"):
                        instantiated.append(m)
                    elif isinstance(m, type):
                        # New collections class requires llm
                        if llm is not None:
                            instantiated.append(m(llm=llm))  # type: ignore[call-arg]
                        else:
                            instantiated.append(m)  # type: ignore
                    else:
                        instantiated.append(m)
                except Exception as ce:
                    logger.debug("Metric instantiation failed for %s: %s", m, ce)
                    instantiated.append(m)

            kwargs: dict[str, Any] = {"metrics": instantiated}
            if llm is not None:
                kwargs["llm"] = llm
            # Intentionally not passing embeddings to avoid OpenAIEmbeddings.embed_query mismatch

            scores = self._evaluate(dataset, **kwargs)  # type: ignore[misc]

            # ragas returns dict-like with keys matching metric names; handle both underscore and original
            import math

            def _get(name: str) -> float:
                val = 0.0
                if isinstance(scores, dict):
                    val = float(scores.get(name, 0.0) or 0.0)
                else:
                    try:
                        val = float(scores[name][0] if hasattr(scores, "__getitem__") else 0.0)
                    except Exception:
                        val = 0.0
                # NaN check — fallback to heuristic for that metric only
                if isinstance(val, float) and math.isnan(val):
                    return float("nan")
                return val

            ragas_result = EvalResult(
                faithfulness=_get("faithfulness"),
                answer_relevancy=_get("answer_relevancy"),
                context_precision=_get("context_precision"),
                context_recall=_get("context_recall"),
            )
            # Per-metric nan fallback to heuristic (preserves other ragas scores)
            if any(math.isnan(getattr(ragas_result, k)) for k in ("faithfulness","answer_relevancy","context_precision","context_recall")):
                heur = self._evaluate_heuristic(samples)
                for k in ("faithfulness","answer_relevancy","context_precision","context_recall"):
                    if math.isnan(getattr(ragas_result, k)):
                        setattr(ragas_result, k, getattr(heur, k))
                        logger.debug("RAGAS %s was nan, replaced with heuristic %.3f", k, getattr(heur, k))
                # Keep ragas error for transparency if any nan
                if any(math.isnan(_get(k)) for k in ("faithfulness","answer_relevancy","context_precision","context_recall")):
                    ragas_result.error = "partial nan fallback to heuristic"
            return ragas_result

        except Exception as exc:
            logger.warning("RAGAS evaluation failed (%s), falling back to heuristic scoring.", exc)
            heur = self._evaluate_heuristic(samples)
            heur.error = str(exc)
            return heur

    # ------------------------------------------------------------------
    # Heuristic fallback path — deterministic token-overlap (F1)
    # ------------------------------------------------------------------

    # Minimal English stopwords — no dependency needed
    _STOPWORDS: set[str] = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "am", "it", "its",
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "they",
        "them", "his", "her", "this", "that", "these", "those", "what",
        "which", "who", "whom", "how", "when", "where", "why", "if", "or",
        "and", "but", "not", "no", "nor", "so", "as", "at", "by", "for",
        "in", "of", "on", "to", "up", "with", "from", "into", "about",
        "than", "then", "also", "just", "more", "most", "very", "too",
        "each", "every", "all", "any", "both", "few", "many", "much",
        "own", "other", "some", "such", "only", "same", "there", "here",
    }

    _ABSENCE_MARKERS: tuple[str, ...] = (
        # Knowledge absence
        "not found in", "not contain information", "not mention",
        "no information", "not available in", "not provided in",
        "not stated in", "not specified in", "absent from",
        "no relevant", "no data", "did not exist",
        # Refusal / safety
        "cannot fulfill", "cannot execute", "cannot comply",
        "i cannot", "should not be used",
        "strictly contraindicated",
    )

    @classmethod
    def _content_tokens(cls, text: str) -> set[str]:
        """Extract content tokens (lowercase, stopwords removed)."""
        return {t for t in text.lower().split() if t not in cls._STOPWORDS and len(t) > 1}

    @classmethod
    def _f1(cls, predicted: set[str], reference: set[str]) -> float:
        """Token-level F1 between two sets."""
        if not predicted or not reference:
            return 0.0
        # Exact matches
        overlap = len(predicted & reference)
        # Fuzzy: also count substring containment for unmatched tokens
        # e.g. "cache" in "caching", "configure" in "configuration"
        pred_unmatched = predicted - reference
        ref_unmatched = reference - predicted
        for pt in pred_unmatched:
            for rt in ref_unmatched:
                if len(pt) >= 4 and len(rt) >= 4 and (pt in rt or rt in pt):
                    overlap += 1
                    ref_unmatched = ref_unmatched - {rt}
                    break
        precision = min(overlap, len(predicted)) / len(predicted)
        recall = min(overlap, len(reference)) / len(reference)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _evaluate_heuristic(self, samples: list[EvalSample]) -> EvalResult:
        """Compute heuristic scores when RAGAS is not available.

        Faithfulness: F1 between answer content tokens and context tokens.
        Answer Relevancy: F1 between question content tokens and answer tokens,
            with full credit for correct absence declarations.
        Context Precision: F1 between expected answer tokens and context tokens.
        Context Recall: same as precision for heuristic.
        """
        total_faith = total_rel = total_prec = total_rec = 0.0

        for sample in samples:
            answer_content = self._content_tokens(sample.actual_answer)
            context_text = " ".join(sample.retrieved_contexts or sample.contexts)
            context_content = self._content_tokens(context_text)
            question_content = self._content_tokens(sample.query)
            expected_content = self._content_tokens(sample.expected_answer)

            # Absence detection — shared across all metrics
            expected_lower = sample.expected_answer.lower()
            actual_lower = sample.actual_answer.lower()
            expected_is_absence = any(m in expected_lower for m in self._ABSENCE_MARKERS)
            actual_is_absence = any(m in actual_lower for m in self._ABSENCE_MARKERS)

            if expected_is_absence and actual_is_absence:
                # Correctly refused to answer — full credit on all axes
                total_faith += 1.0
                total_rel += 1.0
                total_prec += 1.0
                total_rec += 1.0
            elif expected_is_absence:
                # Expected absence but answer didn't refuse — penalise
                total_faith += 0.0
                total_rel += 0.0
                total_prec += 0.0
                total_rec += 0.0
            else:
                # Normal sample — token-F1 scoring
                total_faith += self._f1(answer_content, context_content)

                q_a_f1 = self._f1(question_content, answer_content)
                e_a_f1 = self._f1(expected_content, answer_content)
                total_rel += max(q_a_f1, e_a_f1)

                if expected_content and context_content:
                    ctx_f1 = self._f1(expected_content, context_content)
                    total_prec += ctx_f1
                    total_rec += ctx_f1
                else:
                    total_prec += 0.0
                    total_rec += 0.0

        n = len(samples)
        return EvalResult(
            faithfulness=total_faith / n,
            answer_relevancy=total_rel / n,
            context_precision=total_prec / n,
            context_recall=total_rec / n,
        )


# ---------------------------------------------------------------------------
# FastRegressionEvaluator — explicit heuristic-only alias
# ---------------------------------------------------------------------------

class FastRegressionEvaluator(RAGASEvaluator):
    """Deterministic zero-cost evaluator for local regression tests.

    Always uses token-overlap heuristic regardless of RAGAS availability.
    Use for cheap CI smoke tests. For semantic evaluation use RAGASEvaluator.
    """

    def evaluate_samples(self, samples: list[EvalSample], force_heuristic: bool = True) -> EvalResult:  # type: ignore[override]
        # Force heuristic irrespective of caller arg (but respect explicit False if subclass wants)
        return super().evaluate_samples(samples, force_heuristic=True)


# ---------------------------------------------------------------------------
# Convenience: one-shot offline evaluation
# ---------------------------------------------------------------------------

def run_offline_evaluation(
    queries: list[str],
    expected_answers: list[str],
    contexts: list[list[str]],
    actual_answers: list[str],
    retrieved_contexts: Optional[list[list[str]]] = None,
    llm_config: Optional[dict] = None,
) -> EvalResult:
    """Run offline RAGAS evaluation on pipeline outputs.

    Parameters
    ----------
    queries:
        The input queries for each sample.
    expected_answers:
        Ground-truth / reference answers.
    contexts:
        The relevant context passages for each query.
    actual_answers:
        The answers produced by the RAG pipeline.
    retrieved_contexts:
        The contexts actually retrieved by the pipeline (if different
        from the gold ``contexts``). Useful for measuring retrieval quality.
    llm_config:
        Optional dict with ``{"api_key": "sk-...", "model": "gpt-4", "base_url": "https://..."}``
        passed to RAGAS. Also supports ``embedding_model``.

    Returns
    -------
    EvalResult
        Aggregated metric scores.
    """
    if retrieved_contexts is None:
        retrieved_contexts = contexts  # assume ideal retrieval for offline

    lengths = {len(lst) for lst in (queries, expected_answers, contexts, actual_answers, retrieved_contexts)}
    if len(lengths) > 1:
        raise ValueError(
            f"All input lists must have the same length. Got: "
            f"queries={len(queries)}, expected_answers={len(expected_answers)}, "
            f"contexts={len(contexts)}, actual_answers={len(actual_answers)}, "
            f"retrieved_contexts={len(retrieved_contexts)}"
        )

    samples = [
        EvalSample(
            query=q,
            expected_answer=ea,
            contexts=ctx,
            actual_answer=aa,
            retrieved_contexts=rc,
        )
        for q, ea, ctx, aa, rc in zip(
            queries, expected_answers, contexts, actual_answers, retrieved_contexts
        )
    ]

    evaluator = RAGASEvaluator(llm_config=llm_config)
    return evaluator.evaluate_samples(samples)


# Alias for backwards compatibility with service container
EvaluationAgent = RAGASEvaluator
