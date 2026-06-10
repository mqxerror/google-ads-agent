"""Token estimation and context budget management.

Uses character-based heuristic (1 token ~ 4 chars) to estimate token usage
and enforce budget limits across context layers with priority-based allocation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Approximate chars per token for English text (Claude BPE tokenizer averages ~3.5-4)
CHARS_PER_TOKEN = 4

# Model context windows (input tokens)
MODEL_CONTEXT_LIMITS = {
    "claude-fable-5[1m]": 1_000_000,
    "claude-fable-5": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-haiku-4-5-20251001": 200_000,
}

# Priority levels — lower number = higher priority
P_CRITICAL = 0      # Never drop: system instructions, MCP tools, marketing intelligence
P_IMPORTANT = 1     # Compress but keep: business context, guidelines, campaign memory
P_NICE_TO_HAVE = 2  # Truncate aggressively: live data, recent messages
P_DROPPABLE = 3     # Drop first: session summaries, account insights


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


@dataclass
class TokenBudget:
    """Token budget for a model."""
    model_id: str
    max_context: int
    safety_ratio: float = 0.85  # Use 85% of context max
    max_output: int = 8192

    @property
    def effective_input_budget(self) -> int:
        """Usable input tokens after safety margin and output reservation."""
        return int(self.max_context * self.safety_ratio) - self.max_output

    @classmethod
    def for_model(cls, model_id: str) -> TokenBudget:
        max_ctx = MODEL_CONTEXT_LIMITS.get(model_id, 200_000)
        return cls(model_id=model_id, max_context=max_ctx)


@dataclass
class LayerAllocation:
    """A context layer with its content, priority, and token estimate."""
    name: str
    content: str
    priority: int  # 0=critical ... 3=droppable
    estimated_tokens: int = 0
    allocated_tokens: int = 0
    was_truncated: bool = False
    was_dropped: bool = False

    def __post_init__(self):
        self.estimated_tokens = estimate_tokens(self.content)
        self.allocated_tokens = self.estimated_tokens


@dataclass
class BudgetResult:
    """Result of budget allocation across layers."""
    layers: list[LayerAllocation]
    total_tokens: int = 0
    budget: int = 0
    budget_remaining: int = 0
    usage_ratio: float = 0.0
    warnings: list[str] = field(default_factory=list)
    dropped_layers: list[str] = field(default_factory=list)

    @property
    def usage_percent(self) -> int:
        """Usage as integer percentage (0-100).

        For large context models (1M), use a practical ceiling so the bar
        actually shows meaningful progress. 100K is a practical limit for
        a single conversation turn's context.
        """
        practical_ceiling = min(self.budget, 100_000)
        if practical_ceiling <= 0:
            return 0
        return min(100, int((self.total_tokens / practical_ceiling) * 100))


def allocate_budget(layers: list[LayerAllocation], budget: TokenBudget) -> BudgetResult:
    """Allocate token budget across layers by priority.

    Strategy:
    1. Sum all layer tokens
    2. If under budget, keep everything
    3. If over budget, truncate/drop layers starting from lowest priority (P3 → P0)
    """
    effective = budget.effective_input_budget
    total = sum(la.estimated_tokens for la in layers)

    result = BudgetResult(layers=layers, budget=effective)

    if total <= effective:
        # Everything fits
        result.total_tokens = total
        result.budget_remaining = effective - total
        result.usage_ratio = total / effective if effective > 0 else 0
        return result

    # Over budget — need to trim
    overshoot = total - effective
    result.warnings.append(f"Context exceeds budget by ~{overshoot} tokens. Trimming lower-priority layers.")

    # Sort by priority descending (drop P3 first, then P2, etc.)
    # Within same priority, drop larger layers first
    sorted_layers = sorted(layers, key=lambda la: (-la.priority, -la.estimated_tokens))

    remaining_to_cut = overshoot

    for la in sorted_layers:
        if remaining_to_cut <= 0:
            break

        if la.priority >= P_DROPPABLE:
            # Drop entirely
            remaining_to_cut -= la.estimated_tokens
            la.was_dropped = True
            la.allocated_tokens = 0
            la.content = ""
            result.dropped_layers.append(la.name)
            result.warnings.append(f"Dropped '{la.name}' ({la.estimated_tokens} tokens)")

        elif la.priority >= P_NICE_TO_HAVE:
            # Truncate to half, or drop if still not enough
            if la.estimated_tokens > 500:
                target = max(la.estimated_tokens // 2, 200)
                saved = la.estimated_tokens - target
                la.content = truncate_preserving_structure(la.content, target * CHARS_PER_TOKEN)
                la.allocated_tokens = target
                la.was_truncated = True
                remaining_to_cut -= saved
                result.warnings.append(f"Truncated '{la.name}' from {la.estimated_tokens} to ~{target} tokens")

        elif la.priority >= P_IMPORTANT:
            # Only truncate if desperate — keep at least 30%
            if remaining_to_cut > 0 and la.estimated_tokens > 300:
                target = max(int(la.estimated_tokens * 0.3), 200)
                saved = la.estimated_tokens - target
                la.content = truncate_preserving_structure(la.content, target * CHARS_PER_TOKEN)
                la.allocated_tokens = target
                la.was_truncated = True
                remaining_to_cut -= saved
                result.warnings.append(f"Compressed '{la.name}' to ~{target} tokens (was {la.estimated_tokens})")

        # P_CRITICAL layers are never touched

    # Recalculate totals
    result.total_tokens = sum(la.allocated_tokens for la in layers)
    result.budget_remaining = effective - result.total_tokens
    result.usage_ratio = result.total_tokens / effective if effective > 0 else 0

    return result


def truncate_preserving_structure(text: str, max_chars: int) -> str:
    """Truncate text while preserving markdown structure.

    Keeps the first portion and last portion, with a truncation marker in between.
    Tries to break at section headers (## lines) for cleaner cuts.
    """
    if len(text) <= max_chars:
        return text

    # Keep 70% from start, 20% from end, 10% for marker
    head_chars = int(max_chars * 0.7)
    tail_chars = int(max_chars * 0.2)

    head = text[:head_chars]
    tail = text[-tail_chars:] if tail_chars > 0 else ""

    # Try to break at a newline for cleaner output
    last_newline = head.rfind("\n")
    if last_newline > head_chars * 0.5:
        head = head[:last_newline]

    if tail:
        first_newline = tail.find("\n")
        if first_newline > 0:
            tail = tail[first_newline:]

    truncated_chars = len(text) - len(head) - len(tail)
    marker = f"\n\n[... {truncated_chars} chars truncated ...]\n\n"

    return head + marker + tail


def build_layer_breakdown(result: BudgetResult) -> dict:
    """Build a breakdown dict for the frontend context badge."""
    return {
        "total_tokens": result.total_tokens,
        "budget": result.budget,
        "usage_percent": result.usage_percent,
        "usage_ratio": round(result.usage_ratio, 3),
        "layers": [
            {
                "name": la.name,
                "tokens": la.allocated_tokens,
                "priority": la.priority,
                "truncated": la.was_truncated,
                "dropped": la.was_dropped,
            }
            for la in result.layers
        ],
        "warnings": result.warnings,
        "dropped": result.dropped_layers,
    }
