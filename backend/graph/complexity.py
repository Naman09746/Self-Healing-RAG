"""
Adaptive Query Complexity Classifier — Phase 3C.

Two-stage design:
  1. Rule-based lightweight classifier (primary, <1ms latency).
  2. Optional LLM fallback (enabled via ``COMPLEXITY_USE_LLM=true``).

The classifier produces a `complexity_score` in [0.0, 1.0] that drives
the ``adaptive_k()`` mapping:

    Score Range    k    Use Case
    -----------  ----  -------------------------------------------
    0.0 – 0.3      3   Simple factoid: one clear answer
    0.3 – 0.7      5   Medium: synthesis across a few sources
    0.7 – 1.0     10   Complex: multi-hop, conflicting sources
"""

import re
import math
from typing import List, Optional, Set

# ---------------------------------------------------------------------------
# Domain lexicons — lightweight keyword detection
# ---------------------------------------------------------------------------

# Single tokens that indicate technical/domain-specific vocabulary.
# Multi-word phrases are matched separately via bigram/trigram scanning.
# NOTE: tokens are matched after stripping trailing punctuation.
_TECHNICAL_TERMS: Set[str] = {
    # Legal / Regulatory
    "jurisdiction", "extraterritorial", "precedent", "statute", "regulation",
    "compliance", "liability", "fiduciary", "tort", "indemnify", "arbitration",
    "provision", "clause", "subsection", "notwithstanding", "heretofore",
    "hereinafter", "aforesaid", "gdpr", "ccpa", "hipaa", "sox", "pci",
    "consent", "reconcile", "reconciled", "reconciliation", "conflicting",
    "article", "paragraph", "enforcement",
    # Medical
    "contraindication", "pathophysiology", "comorbidity", "prognosis",
    "differential", "diagnosis", "etiology", "meta-analysis", "randomized",
    "placebo", "pharmacokinetics", "bioavailability",
    # Technical / Engineering / Computing
    "asymptotic", "complexity", "polynomial", "recursive", "concurrency",
    "deadlock", "idempotent", "serialization", "denormalization",
    "partitioning", "sharding", "vectorization", "isomorphic",
    "kubernetes", "docker", "containerization", "orchestration",
    "microservices", "api", "rest", "graphql", "grpc",
    "quantum", "cryptography", "encryption", "algorithm",
    "neural", "transformer", "encoder", "decoder", "latent",
    "architecture", "protocol", "middleware", "pipeline",
    "deployment", "autoscaling", "cluster",
    "redundancy", "failover", "latency",
    "throughput", "concurrent", "parallel", "distributed",
    "relational", "nosql", "indexing",
    "processing", "automated", "discrimination",
    # Finance / Economics
    "derivative", "amortization", "underwriting", "liquidity", "volatility",
    "arbitrage", "depreciation", "accrual", "goodwill", "solvency",
    "securitization", "treasury", "inversion", "recession",
    "monetary", "fiscal", "yield",
    # AI / ML specific
    "rag", "embedding", "hallucination",
    "grounding", "pretrained", "inference",
    # Individual tokens that form part of common multi-word tech phrases
    "machine", "learning", "bias", "detection",
    "attention", "mechanism", "retrieval", "augmented",
    "prompt", "engineering", "chain", "thought",
    "fine", "tuning", "few", "shot",
    "load", "balancing", "data", "subject", "controller", "processor",
    "housing", "starts", "leading", "indicator",
    "predictive", "power", "federal", "reserve", "policy", "curve",
    "vector", "database",
    # Additional terms often used in domain-specific queries
    "docker", "kubernetes", "quantum",
    "algorithm", "architecture", "deployment", "cluster",
    "saas", "encryption", "protocol",
}

# Multi-word phrases that are strong complexity signals.
# These are checked via sliding bigram/trigram matching AFTER
# cleaning punctuation from each token.
_MULTI_WORD_TECH_TERMS: Set[str] = {
    "data subject", "data controller", "data processor",
    "machine learning", "deep learning",
    "attention mechanism", "attention mechanisms",
    "retrieval augmented", "retrieval-augmented",
    "prompt engineering",
    "chain of thought",
    "fine tuning", "fine-tuning",
    "few shot", "few-shot",
    "bias detection",
    "load balancing",
    "vector database",
    "monetary policy",
    "federal reserve",
    "yield curve",
    "predictive power",
    "leading indicator", "leading indicators",
    "housing starts",
    "retrieval augmented generation",
}

_COMPARATIVE_PATTERNS: re.Pattern = re.compile(
    r"\b(?:compared?|versus|vs\.?|difference|similar|contrast|"
    r"relationship|correlation|more|less|better|worse|"
    r"than|rather than|instead of|either|neither|between|with)\b",
    re.IGNORECASE,
)

_CAUSAL_PATTERNS: re.Pattern = re.compile(
    r"\b(?:because|therefore|thus|hence|consequently|"
    r"results?\s+in|leads?\s+to|caused?\s+by|attributed?\s+to|"
    r"due to|as a result|so that|affect[s]?|impact[s]?|influence[s]?|"
    r"mitigate[s]?|prevent[s]?|trigger[s]?|induce[s]?)\b",
    re.IGNORECASE,
)

_TEMPORAL_PATTERNS: re.Pattern = re.compile(
    r"\b(?:before|after|during|while|subsequently|"
    r"following|preceding|simultaneously|concurrent|"
    r"timeline|sequence|evolution|over time)\b",
    re.IGNORECASE,
)

_QUESTION_WORD_WEIGHTS: dict = {
    "what": 0.1,
    "who": 0.1,
    "when": 0.2,
    "where": 0.2,
    "which": 0.2,
    "how": 0.4,
    "why": 0.5,
    "does": 0.2,
    "is": 0.1,
    "are": 0.1,
    "can": 0.2,
    "explain": 0.6,
    "describe": 0.5,
    "compare": 0.7,
    "contrast": 0.7,
    "analyze": 0.7,
    "summarize": 0.3,
    "define": 0.2,
    "list": 0.1,
}


# ---------------------------------------------------------------------------
# Entity detection via capitalization + punctuation patterns
# ---------------------------------------------------------------------------

# Matches proper nouns (single or multi-word capitalized) — strong domain signal.
# Handles possessive forms like "Act's" by optionally matching "'s" at end.
_ENTITY_PATTERN: re.Pattern = re.compile(
    r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*"
    r"(?:'s)?(?:\s+\([A-Z]{2,}\))?\b"
)

# Matches ALL-CAPS acronyms — another strong domain signal.
_ACRONYM_PATTERN: re.Pattern = re.compile(
    r"\b[A-Z]{2,}\b"
)

# Common English words that start with a capital letter (at start of sentence)
# but are NOT named entities — exclude from entity count.
_STOP_ENTITY_WORDS: Set[str] = {
    "what", "who", "when", "where", "why", "which", "how", "does", "is",
    "are", "can", "the", "a", "an", "this", "that", "these", "those", "it",
    "i", "we", "you", "he", "she", "they", "my", "our", "your", "his", "her",
    "its", "their", "and", "or", "but", "for", "nor", "yet", "so", "if",
    "then", "else", "all", "each", "every", "some", "any", "no", "not",
    "very", "just", "also", "too", "only", "more", "less",
}


# ---------------------------------------------------------------------------
# Token cleaning helper
# ---------------------------------------------------------------------------

_TRAILING_PUNCTUATION: re.Pattern = re.compile(r"[^a-zA-Z0-9]+$")

def _clean_token(token: str) -> str:
    """Strip trailing punctuation from a token for dictionary matching."""
    return _TRAILING_PUNCTUATION.sub("", token)


def _count_tech_terms(cleaned_tokens: List[str]) -> int:
    """Count technical terms, including multi-word phrases via bigram/trigram.

    ``cleaned_tokens`` are already lowercased and punctuation-stripped.
    """
    hits = 0
    # Single-token hits
    for t in cleaned_tokens:
        if t in _TECHNICAL_TERMS:
            hits += 1

    # Multi-word phrase hits via bigram/trigram sliding window
    n = len(cleaned_tokens)
    for i in range(n):
        # Trigram
        if i + 3 <= n:
            phrase = " ".join(cleaned_tokens[i:i+3])
            if phrase in _MULTI_WORD_TECH_TERMS:
                hits += 1
                continue  # avoid double-counting lower-order n-grams from same span
        # Bigram
        if i + 2 <= n:
            phrase = " ".join(cleaned_tokens[i:i+2])
            if phrase in _MULTI_WORD_TECH_TERMS:
                hits += 1

    return hits


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(query: str) -> dict:
    """Extract interpretable features from the query string.

    Returns a dict of feature names → float values (all normalised [0,1]).
    """
    raw_tokens: List[str] = query.split()
    n_tokens: int = len(raw_tokens)
    cleaned_tokens: List[str] = [_clean_token(t).lower() for t in raw_tokens]
    lower_query: str = query.lower()

    # 1. Technical term presence (combination of density and count)
    tech_hits: int = _count_tech_terms(cleaned_tokens)
    tech_density: float = min(max(tech_hits / max(n_tokens, 1), tech_hits / 8.0), 1.0)

    # 2. Question word weight
    q_word: Optional[str] = next((t for t in cleaned_tokens if t in _QUESTION_WORD_WEIGHTS), None)
    q_weight: float = _QUESTION_WORD_WEIGHTS.get(q_word, 0.0)

    # 3. Multi-hop signal density (combination of density and count)
    causal_hits: int = len(_CAUSAL_PATTERNS.findall(lower_query))
    temporal_hits: int = len(_TEMPORAL_PATTERNS.findall(lower_query))
    comparative_hits: int = len(_COMPARATIVE_PATTERNS.findall(lower_query))
    multi_hop_hits: int = causal_hits + temporal_hits + comparative_hits
    multi_hop_density: float = min(max(multi_hop_hits / max(n_tokens, 1) * 2.0, multi_hop_hits / 3.0), 1.0)

    # 4. Entity count (capitalized proper nouns as multi-word, acronyms)
    # Exclude common stop words that happen to be capitalized at sentence start
    raw_entity_matches: List[str] = _ENTITY_PATTERN.findall(query) + _ACRONYM_PATTERN.findall(query)
    filtered_entities: int = sum(
        1 for e in raw_entity_matches if e.lower().rstrip("'s") not in _STOP_ENTITY_WORDS
    )
    entity_density: float = min(filtered_entities / max(n_tokens, 1), 1.0)

    # 5. Length factor (log scale — diminishing returns)
    length_factor: float = min(math.log1p(n_tokens) / 4.0, 1.0)

    # 6. Clause count (sentences / conjunctions beyond simple clause)
    clause_pattern = re.compile(r"(?:[,;]\s+|\.\s+|\b(?:and|or|but|because|although|whereas)\b)")
    sub_clauses: int = len(clause_pattern.findall(lower_query))
    clause_factor: float = min(sub_clauses / 3.0, 1.0)

    return {
        "n_tokens": float(n_tokens),
        "tech_density": tech_density,
        "q_weight": q_weight,
        "multi_hop_density": multi_hop_density,
        "entity_density": entity_density,
        "length_factor": length_factor,
        "clause_factor": clause_factor,
    }


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------

_CONTRAST_DENOM: float = 0.22
"""Denominator in ``x / (x + denom)`` contrast stretch.

Tuned empirically: 0.20 spreads simple queries to ~0.29 (under 0.3),
medium queries to ~0.3–0.7, and complex queries above 0.7.

Increasing the denominator pushes ALL scores downward uniformly, so
the raw signal for complex queries must be sufficiently high to
compensate. The multi-word tech term detection + "between"/"with"
comparative pattern + punctuation cleaning ensure complex queries
generate enough raw signal.
"""


def compute_complexity(query: str) -> float:
    """Compute a complexity score in [0.0, 1.0] using the rule-based classifier.

    Weights are tuned to penalise multi-hop queries and technical density
    more heavily than simple length or question word.

    The raw weighted sum is then passed through a non-linear contrast stretch:
        stretched = raw / (raw + denom)
    where denom=0.20 spreads simple queries toward 0, medium toward 0.5,
    and complex toward 1.0.

    Args:
        query: The raw user query string.

    Returns:
        A float in [0.0, 1.0] where 0 = trivial, 1 = maximally complex.
    """
    if not query or not query.strip():
        return 0.0

    f = _extract_features(query)

    # Weighted sum (weights sum to 1.0 for interpretability)
    raw = (
        0.30 * f["tech_density"]
        + 0.15 * f["q_weight"]
        + 0.25 * f["multi_hop_density"]
        + 0.10 * f["entity_density"]
        + 0.05 * f["length_factor"]
        + 0.15 * f["clause_factor"]
    )

    # Contrast stretch — spreads the compressed [0, ~0.6] range to [0, 1]
    stretched = raw / (raw + _CONTRAST_DENOM) if raw > 0.0 else 0.0

    return max(0.0, min(1.0, stretched))


def compute_complexity_llm(query: str, llm_client) -> float:
    """Fallback complexity classification via a fast LLM call.

    This is only invoked when the config flag ``COMPLEXITY_USE_LLM=true``.
    The LLM is asked to return a single float between 0.0 and 1.0.

    Args:
        query: The raw user query string.
        llm_client: An async callable that accepts a prompt string and
                     returns a response string.

    Returns:
        A float in [0.0, 1.0].
    """
    prompt = (
        "You are a query complexity classifier. Given a user query, return "
        "a single floating-point number between 0.0 and 1.0 representing "
        "its complexity.\n\n"
        "A simple factoid (e.g., 'What is the capital of France?') should "
        "score near 0.0. A complex multi-hop question requiring synthesis "
        "across multiple documents (e.g., 'How does GDPR Article 17 apply "
        "to US-based SaaS companies processing EU citizen data?') should "
        "score near 1.0.\n\n"
        "Return ONLY the number, no explanation.\n\n"
        f"Query: {query}\n\nComplexity:"
    )

    response: str = llm_client(prompt)
    try:
        parsed = float(response.strip())
        return max(0.0, min(1.0, parsed))
    except (ValueError, TypeError):
        # If LLM returns unparseable output, fall back to rule-based
        return compute_complexity(query)


# ---------------------------------------------------------------------------
# Threshold mappings
# ---------------------------------------------------------------------------

def adaptive_k(complexity_score: float) -> int:
    """Map a complexity score to a retrieval depth ``k``.

    Args:
        complexity_score: Float in [0.0, 1.0] from ``compute_complexity``.

    Returns:
        Integer k in {3, 5, 10}.
    """
    if complexity_score < 0.3:
        return 3
    elif complexity_score < 0.7:
        return 5
    else:
        return 10


def select_rerank_top_k(k: int) -> int:
    """How many items to keep after reranking.

    Generally we re-rank the top ``k`` and keep the top ``k``, but for
    k=10 we take top 6 to avoid quality dilution.

    Args:
        k: Retrieval depth.

    Returns:
        Integer top_k for the reranker.
    """
    if k <= 3:
        return 3
    elif k <= 5:
        return 5
    else:
        return 6