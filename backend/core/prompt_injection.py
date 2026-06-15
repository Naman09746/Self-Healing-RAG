"""
Prompt Injection Detection (Phase 6).

Detects common prompt injection patterns in user queries before they reach the
LLM. Uses regex-based detection with configurable sensitivity.

Returns a structured result with threat score, severity, and matched patterns.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class InjectionResult:
    """Result of a prompt injection check."""

    is_threat: bool = False
    score: float = 0.0  # 0.0 (safe) to 1.0 (malicious)
    severity: str = "none"  # none | low | medium | high | critical
    matched_patterns: List[str] = field(default_factory=list)
    query_hash: str = ""


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each pattern is a (name, compiled_regex, weight) tuple.
# weight contributes to the overall threat score.

_PATTERNS: List[Tuple[str, re.Pattern, float]] = [
    # ---- Role-play / system prompt bypass ----
    (
        "role_play_ignore",
        re.compile(
            r"(?i)(?:ignore|forget|disregard|override)\s+"
            r"(?:all\s+)?(?:previous\s+)?(?:instructions?|prompts?|commands?|rules?)"
        ),
        0.8,
    ),
    (
        "role_play_act_as",
        re.compile(
            r"(?i)(?:you\s+are\s+(?:now\s+|not\s+)?|act\s+as\s+|pretend\s+(?:to\s+be\s+|that\s+))"
            r"(?:an?\s+)?(?:different|new|unrestricted|unfiltered|evil|malicious|hacker|criminal)"
        ),
        0.7,
    ),
    (
        "role_play_system_prompt",
        re.compile(
            r"(?i)(?:system\s+(?:prompt|message|instruction)|"
            r"new\s+(?:system\s+)?(?:prompt|instruction)|"
            r"override\s+(?:system|default)\s+(?:prompt|behavior|config))"
        ),
        0.9,
    ),
    (
        "role_play_dan",
        re.compile(
            r"(?i)(?:do\s+(?:not|n't)\s+(?:have\s+)?(?:any\s+)?(?:restrictions?|limits?|"
            r"boundaries?|filters?|guidelines?|policies?|rules?)|"
            r"unfiltered\s+(?:access|mode|response)|"
            r"dan\s+mode|jailbreak(?:ed|ing)?)"
        ),
        0.9,
    ),
    # ---- Direct injection ----
    (
        "direct_injection_instruction",
        re.compile(
            r"(?i)(?:say\s+\"?yes\"?\s+(?:if|when|and)|"
            r"repeat\s+(?:exactly|the\s+(?:following|above|previous))\s+(?:text|phrase|sentence|prompt|word)|"
            r"output\s+(?:the\s+)?(?:following|above|previous)\s+(?:text|prompt|instruction))"
        ),
        0.8,
    ),
    (
        "direct_injection_template",
        re.compile(
            r"(?i)(?:\{\{.*?}}|%\{\s*.*?\s*}%|<\|.*?\|>|```\s*(?:system|user|assistant))"
        ),
        0.5,
    ),
    # ---- Delimiter confusion / encoding tricks ----
    (
        "encoding_base64",
        re.compile(
            r"(?i)(?:base64|b64|base64\s*(?:encode|decode)|"
            r"[A-Za-z0-9+/]{40,}={0,2})"
            r"(?:\s*(?:encode|decode|string|text|prompt|instruction))?"
        ),
        0.6,
    ),
    (
        "encoding_hex",
        re.compile(r"(?i)(?:\b(?:0x[0-9a-fA-F]{16,}|[0-9a-fA-F]{32,})\b)"),
        0.3,
    ),
    # ---- Context override ----
    (
        "context_override",
        re.compile(
            r"(?i)(?:new\s+(?:session|conversation|chat|prompt)|"
            r"reset\s+(?:context|session|conversation|memory)|"
            r"clear\s+(?:your\s+)?(?:memory|context|history|state)|"
            r"start\s+(?:over|fresh|new|again))"
        ),
        0.6,
    ),
    (
        "context_injection",
        re.compile(
            r"(?i)(?:<<(?:\s*SYSTEM|USER|ASSISTANT|PROMPT)\s*>>|"
            r"<\|im_start\|>\s*(?:user|system|assistant)|"
            r"<\|im_end\|>)"
        ),
        0.9,
    ),
    # ---- XSS / markdown injection ----
    (
        "xss_script_tag",
        re.compile(
            r"(?i)<\s*script[^>]*>.*?<\s*/\s*script\s*>",
            re.DOTALL,
        ),
        0.7,
    ),
    (
        "xss_event_handler",
        re.compile(
            r"(?i)\bon\w+\s*=\s*(?:\"|'|`)[^\"'`]*(?:\"|'|`)"
        ),
        0.6,
    ),
    (
        "markdown_injection",
        re.compile(
            r"(?i)(?:\[.*?\]\s*\(.*?\)|!"
            r"\[.*?\]\s*\(.*?\)|```[a-z]*\s*\n.*?\n```)",
        ),
        0.3,
    ),
    # ---- Data exfiltration attempts ----
    (
        "exfiltrate_api_keys",
        re.compile(
            r"(?i)(?:sk-[A-Za-z0-9]{20,}|api[_-]?key[=:]\s*[\"']?[A-Za-z0-9]{16,}|"
            r"access[_-]?token[=:]\s*[\"']?[A-Za-z0-9]{16,}|"
            r"AIza[0-9A-Za-z\-_]{35}|aws[_-]?[a-z0-9]{16,})"
        ),
        0.8,
    ),
    (
        "exfiltrate_urls",
        re.compile(
            r"(?i)(?:https?:\/\/(?:localhost|127\.0\.0\.1|10\.|172\.(?:1[6-9]|2\d|3[01])|192\.168)"
            r"(?::\d+)?(?:\/|$))"
        ),
        0.7,
    ),
    # ---- Prompt leaking ----
    (
        "prompt_leak",
        re.compile(
            r"(?i)(?:print|show|display|reveal|output|dump|leak|expose)\s+"
            r"(?:(?:your|the)\s+)?(?:system\s+)?(?:prompt|instruction|command|directive|"
            r"prompt\s+template|system\s+message|initial\s+prompt)"
        ),
        0.9,
    ),
]


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def check_prompt_injection(query: str) -> InjectionResult:
    """Check a query for prompt injection patterns.

    Parameters
    ----------
    query : str
        The user's query text.

    Returns
    -------
    InjectionResult
        Detection result with score, severity, and matched patterns.
    """
    result = InjectionResult(query_hash=_hash_query(query))
    matched_names: List[str] = []
    total_score = 0.0

    for name, pattern, weight in _PATTERNS:
        if pattern.search(query):
            matched_names.append(name)
            total_score += weight
            logger.debug(
                "Prompt injection pattern matched",
                pattern=name,
                weight=weight,
            )

    if matched_names:
        # Score is the max weight, capped at 1.0 (normalized)
        result.score = min(total_score, 1.0)
        result.matched_patterns = matched_names
        result.is_threat = result.score >= settings.PROMPT_INJECTION_THRESHOLD

        # Determine severity
        if result.score >= 0.9:
            result.severity = "critical"
        elif result.score >= 0.7:
            result.severity = "high"
        elif result.score >= 0.5:
            result.severity = "medium"
        else:
            result.severity = "low"

        logger.info(
            "Prompt injection detected",
            score=result.score,
            severity=result.severity,
            patterns=matched_names,
        )

    return result