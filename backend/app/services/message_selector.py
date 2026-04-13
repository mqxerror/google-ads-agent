"""Relevance-based message selection for agent context.

Replaces the naive "last 10 messages" with keyword-overlap scoring
so the agent sees the most relevant past messages for the current query.
"""

from __future__ import annotations

import math
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Stop words to exclude from keyword matching
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "over", "about", "against", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some",
    "such", "no", "only", "own", "same", "than", "too", "very",
    "just", "also", "then", "now", "here", "there", "when", "where",
    "why", "how", "what", "which", "who", "whom", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them",
    "their", "up", "out", "if", "because", "while", "although",
    "let", "please", "thanks", "thank", "yes", "no", "ok", "okay",
})


def _tokenize(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


@dataclass
class ScoredMessage:
    """A message with relevance and recency scores."""
    index: int           # Original position in conversation
    role: str
    content: str
    created_at: str
    relevance_score: float
    recency_score: float
    combined_score: float
    is_pinned: bool = False  # Always-include messages (last 2)


def select_relevant_messages(
    query: str,
    messages: list[dict],
    max_messages: int = 12,
    max_tokens: int | None = None,
    relevance_weight: float = 0.7,
    recency_weight: float = 0.3,
    pin_last_n: int = 2,
) -> list[ScoredMessage]:
    """Select the most relevant messages for the current query.

    Args:
        query: Current user message
        messages: All conversation messages (chronological order)
        max_messages: Maximum messages to return
        max_tokens: Optional token budget (chars / 4)
        relevance_weight: Weight for keyword overlap score
        recency_weight: Weight for recency score
        pin_last_n: Always include the last N messages
    """
    if not messages:
        return []

    if len(messages) <= max_messages:
        # All messages fit — return them all
        return [
            ScoredMessage(
                index=i, role=m["role"], content=m["content"],
                created_at=m.get("created_at", ""),
                relevance_score=1.0, recency_score=1.0, combined_score=1.0,
                is_pinned=True,
            )
            for i, m in enumerate(messages)
        ]

    query_tokens = _tokenize(query)
    total = len(messages)
    scored: list[ScoredMessage] = []

    for i, msg in enumerate(messages):
        msg_tokens = _tokenize(msg["content"])
        relevance = _jaccard(query_tokens, msg_tokens)

        # Exponential recency decay — most recent = 1.0, oldest ≈ 0.0
        position_ratio = i / max(total - 1, 1)  # 0.0 (oldest) to 1.0 (newest)
        recency = math.exp(-3 * (1 - position_ratio))  # e^(-3) ≈ 0.05 for oldest

        combined = relevance_weight * relevance + recency_weight * recency

        # Boost messages that contain decisions or actions
        content_lower = msg["content"].lower()
        if any(kw in content_lower for kw in ["decided", "recommend", "changed", "paused", "enabled", "added", "removed", "created"]):
            combined *= 1.3

        scored.append(ScoredMessage(
            index=i, role=msg["role"], content=msg["content"],
            created_at=msg.get("created_at", ""),
            relevance_score=relevance, recency_score=recency,
            combined_score=combined,
        ))

    # Pin the last N messages (always included)
    pinned = scored[-pin_last_n:]
    for sm in pinned:
        sm.is_pinned = True

    # Select from remaining by score
    candidates = scored[:-pin_last_n] if pin_last_n < len(scored) else []
    candidates.sort(key=lambda sm: sm.combined_score, reverse=True)

    remaining_slots = max_messages - len(pinned)
    selected = candidates[:remaining_slots]

    # Combine pinned + selected, sort by original index (chronological)
    result = sorted(pinned + selected, key=lambda sm: sm.index)

    # Apply token budget if specified
    if max_tokens:
        from app.services.token_counter import estimate_tokens
        budget_remaining = max_tokens
        trimmed = []
        for sm in result:
            tokens = estimate_tokens(sm.content)
            if budget_remaining - tokens >= 0 or sm.is_pinned:
                trimmed.append(sm)
                budget_remaining -= tokens
        result = trimmed

    return result


def format_selected_messages(messages: list[ScoredMessage]) -> str:
    """Format selected messages for the agent prompt."""
    if not messages:
        return ""
    parts = []
    for sm in messages:
        role = "User" if sm.role == "user" else "Assistant"
        parts.append(f"{role}: {sm.content}")
    return "\n".join(parts)
