"""Query rewriter — Phase 3B.

Accepts a healing_target parameter that tailors the rewrite strategy:
  - "targeted_healing"     → focused refinement of partial claims
  - "retrieval_expansion"  → broaden query for wider semantic match
  - "aggressive_rewrite"   → complete reformulation (contradiction recovery)
  - "" (empty)             → standard rewrite (legacy / binary mode)
"""

from backend.core.logging import get_logger
from backend.agents.generation.llm_client import LLMClient

logger = get_logger(__name__)

# ── prompt templates per healing target ────────────────────────────────

_PROMPT_TEMPLATES = {
    "targeted_healing": (
        "You are an expert search engineer. The previous answer was partially supported "
        "by the retrieved documents — some claims had evidence but lacked full support.\n\n"
        "ORIGINAL QUERY: {query}\n"
        "FAILURE CONTEXT: {error_context}\n\n"
        "Refine the query to retrieve documents that fill the gaps in the partial answer. "
        "Focus on the specific claims that were unsupported.\n\n"
        "Provide ONLY the rewritten query text. No preamble or explanation.\n\n"
        "REWRITTEN QUERY:"
    ),
    "retrieval_expansion": (
        "You are an expert search engineer. The previous retrieval returned documents that "
        "did not contain evidence for the answer's claims.\n\n"
        "ORIGINAL QUERY: {query}\n"
        "FAILURE CONTEXT: {error_context}\n\n"
        "Broaden the query to cast a wider net. Add synonyms, related concepts, and "
        "alternative phrasings. Prioritize recall over precision.\n\n"
        "Provide ONLY the rewritten query text. No preamble or explanation.\n\n"
        "REWRITTEN QUERY:"
    ),
    "aggressive_rewrite": (
        "You are an expert search engineer. The previous answer contained claims that "
        "were either contradicted by the retrieved documents or could not be extracted at all. "
        "This indicates a fundamental retrieval–generation mismatch.\n\n"
        "ORIGINAL QUERY: {query}\n"
        "FAILURE CONTEXT: {error_context}\n\n"
        "Completely rewrite the query from scratch. Use different keywords, restructure "
        "the intent, and try alternative technical language. Consider what documents would "
        "need to exist to disprove the contradicted claims.\n\n"
        "Provide ONLY the rewritten query text. No preamble or explanation.\n\n"
        "REWRITTEN QUERY:"
    ),
}

_LEGACY_TEMPLATE = """You are an expert search engineer. The following query failed to retrieve relevant documents or produced unsatisfactory results.

ORIGINAL QUERY: {query}
FAILURE CONTEXT: {error_context}

Rewrite this query into a more effective search string. Focus on:
1. Clarifying ambiguous terms.
2. Adding relevant synonyms or technical keywords.
3. Rephrasing for better semantic matching.

Provide ONLY the rewritten query text. No preamble or explanation.

REWRITTEN QUERY:"""


class QueryRewriter:
    def __init__(self, model: str = None):
        self.client = LLMClient(model=model)

    async def rewrite_query(
        self,
        original_query: str,
        error_context: str = "",
        healing_target: str = "",
    ) -> str:
        """Rewrite the query with a strategy tailored to the healing target.

        Parameters
        ----------
        original_query : str
            The original user query.
        error_context : str
            Context describing what went wrong (error logs, grounding feedback).
        healing_target : str
            Phase 3B healing strategy: "targeted_healing", "retrieval_expansion",
            "aggressive_rewrite", or "" for legacy/fallback.

        Returns
        -------
        str
            The rewritten query (or original on failure).
        """
        template = _PROMPT_TEMPLATES.get(healing_target, _LEGACY_TEMPLATE)
        prompt = template.format(
            query=original_query,
            error_context=error_context,
        )

        logger.info(
            "Rewriting query",
            healing_target=healing_target or "legacy",
        )

        try:
            rewritten = (await self.client.generate(prompt)).strip()
            logger.info("Query rewritten", rewritten=rewritten[:80])
            return rewritten
        except Exception as e:
            logger.error("Query rewriting failed", error=str(e))
            return original_query  # Fallback to original