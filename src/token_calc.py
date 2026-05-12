"""
token_calc.py — Token estimation model for BurnRate Phase 1.

See ../docs/methodology.md for the full reasoning. Short version:
  - Visible text is counted exactly via tiktoken (preferred) or chars/3.5.
  - Tool I/O is estimated from a per-tool default table; calibrated.
  - Per-turn billed input = system_prompt + cumulative prior context + this turn's user input.
  - Per-turn billed output = assistant message tokens.

This module is intentionally pure (no I/O), so it's easy to unit-test
and re-run after calibration changes.
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import Iterable

# ---- Optional tiktoken --------------------------------------------------
try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
    HAVE_TIKTOKEN = True
except Exception:
    _ENCODER = None
    HAVE_TIKTOKEN = False


# ---- Tunable defaults ---------------------------------------------------
# Override at runtime by reading meta table or passing to functions.

CHARS_PER_TOKEN_DEFAULT = 3.5
SYSTEM_PROMPT_EST_TOKENS_DEFAULT = 12_000  # Cowork mode system prompt + tools
TOOL_INPUT_EST_TOKENS_DEFAULT = 50         # avg args size per tool call

# Order matters: more specific patterns first.
TOOL_RESULT_DEFAULTS: list[tuple[str, int]] = [
    # (regex pattern, default est tokens)
    (r"^Read$",                          2500),
    (r"^Write$",                           50),
    (r"^Edit$",                           100),
    (r"^Glob$",                           300),
    (r"^Grep$",                           800),
    (r"^Bash$",                           600),
    (r"^WebFetch$",                      4000),
    (r"^WebSearch$",                     1500),
    (r"^Task$|^Agent$",                  3000),
    (r"^TodoWrite$|^Task(Create|Update|List|Get|Stop)$", 100),
    (r"^AskUserQuestion$",                200),
    (r"^Skill$",                          500),
    (r"^ToolSearch$",                     400),
    (r"^mcp__workspace__bash$",           600),
    (r"^mcp__workspace__web_fetch$",     4000),
    (r"^mcp__session_info__list_sessions$",  300),
    (r"^mcp__session_info__read_transcript$", 2000),
    (r"^mcp__cowork__create_artifact$",   200),
    (r"^mcp__cowork__update_artifact$",   200),
    (r"^mcp__cowork__list_artifacts$",    100),
    (r"^mcp__cowork__request_cowork_directory$", 100),
    (r"^mcp__visualize__",                800),
    (r"^mcp__plugin_",                    300),  # auth flows etc
    (r"^mcp__c6bed854",                  1500),  # linear-style heavy connector
    (r"^mcp__",                           500),  # generic MCP fallback
]
TOOL_RESULT_FALLBACK = 500


# ---- Core estimators ----------------------------------------------------

def count_text_tokens(text: str, *, chars_per_token: float = CHARS_PER_TOKEN_DEFAULT) -> int:
    """
    Estimate tokens in a text segment.
    Uses tiktoken's cl100k_base if available, else char-based fallback.
    """
    if not text:
        return 0
    if HAVE_TIKTOKEN:
        try:
            return len(_ENCODER.encode(text))
        except Exception:
            pass
    return math.ceil(len(text) / max(0.1, chars_per_token))


def estimate_tool_result_tokens(tool_name: str) -> int:
    """Look up estimated tokens for a tool result by tool name."""
    for pat, val in TOOL_RESULT_DEFAULTS:
        if re.match(pat, tool_name):
            return val
    return TOOL_RESULT_FALLBACK


def estimate_tool_io_tokens(tool_calls: Iterable[str]) -> int:
    """
    Estimate combined input+output token cost for all tool calls in a turn.
    `tool_calls` is an iterable of tool name strings.
    """
    total = 0
    for name in tool_calls:
        total += TOOL_INPUT_EST_TOKENS_DEFAULT
        total += estimate_tool_result_tokens(name)
    return total


# ---- Per-turn billed-input / billed-output -----------------------------

@dataclass
class TurnEstimate:
    turn_index: int
    role: str                       # 'user' or 'assistant'
    user_msg_chars: int = 0
    assistant_msg_chars: int = 0
    tool_calls: list[str] = field(default_factory=list)

    # Per-turn alone:
    est_user_tokens: int = 0
    est_assistant_tokens: int = 0
    est_tool_io_tokens: int = 0
    est_turn_total_tokens: int = 0

    # Cumulative-as-billed (what Anthropic re-charges):
    est_input_tokens_billed: int = 0
    est_output_tokens_billed: int = 0


def estimate_session(
    turns: list[dict],
    *,
    system_prompt_est_tokens: int = SYSTEM_PROMPT_EST_TOKENS_DEFAULT,
    chars_per_token: float = CHARS_PER_TOKEN_DEFAULT,
) -> list[TurnEstimate]:
    """
    Estimate per-turn token usage for an entire session.

    `turns` is a list of dicts with keys:
        role: 'user' | 'assistant'
        text: str (the visible message text)
        tool_calls: list[str] (tool names called in this turn)

    Returns a list[TurnEstimate] with cumulative billed input populated.

    Billing model (per the methodology doc):
      input_billed_at_t  = system_prompt
                         + sum(visible text + tool I/O for all prior turns)
                         + this_turn user text
                         + this_turn tool I/O
      output_billed_at_t = assistant text at turn t
    """
    estimates: list[TurnEstimate] = []
    cumulative_context = system_prompt_est_tokens

    for i, t in enumerate(turns):
        role = t.get("role", "user")
        text = t.get("text", "") or ""
        tool_calls = list(t.get("tool_calls", []) or [])

        est = TurnEstimate(turn_index=i, role=role, tool_calls=tool_calls)

        if role == "user":
            est.user_msg_chars = len(text)
            est.est_user_tokens = count_text_tokens(text, chars_per_token=chars_per_token)
        else:  # assistant
            est.assistant_msg_chars = len(text)
            est.est_assistant_tokens = count_text_tokens(text, chars_per_token=chars_per_token)

        est.est_tool_io_tokens = estimate_tool_io_tokens(tool_calls)
        est.est_turn_total_tokens = (
            est.est_user_tokens + est.est_assistant_tokens + est.est_tool_io_tokens
        )

        # Billed input at this turn = current cumulative context + this turn's user input + tool I/O
        # Billed output = this turn's assistant text only
        if role == "user":
            est.est_input_tokens_billed = (
                cumulative_context + est.est_user_tokens
            )
            est.est_output_tokens_billed = 0
        else:
            est.est_input_tokens_billed = (
                cumulative_context + est.est_tool_io_tokens
            )
            est.est_output_tokens_billed = est.est_assistant_tokens

        # After processing, this turn's content joins the cumulative context
        cumulative_context += est.est_turn_total_tokens

        estimates.append(est)

    return estimates


def session_summary(estimates: list[TurnEstimate]) -> dict:
    """Aggregate per-session metrics."""
    total_input = sum(e.est_input_tokens_billed for e in estimates)
    total_output = sum(e.est_output_tokens_billed for e in estimates)
    total = total_input + total_output

    # "Unique" content = sum of new content per turn (no re-reads)
    unique_content = sum(e.est_turn_total_tokens for e in estimates)

    # History overhead share = re-read tokens / total input
    history_overhead = max(0, total_input - unique_content)
    history_overhead_share = (history_overhead / total_input) if total_input else 0.0

    return {
        "turns": len(estimates),
        "est_input_tokens": total_input,
        "est_output_tokens": total_output,
        "est_total_tokens": total,
        "est_unique_content_tokens": unique_content,
        "history_overhead_tokens": history_overhead,
        "history_overhead_share": round(history_overhead_share, 4),
    }


if __name__ == "__main__":
    # Quick smoke test mirroring CoPilot's coding-agent scenario
    fake_turns = []
    for i in range(30):
        fake_turns.append({"role": "user", "text": "do the next thing" * 5,
                          "tool_calls": []})
        fake_turns.append({"role": "assistant",
                          "text": "ok, doing the next thing. " * 30,
                          "tool_calls": ["Read", "Bash", "Edit"]})
    ests = estimate_session(fake_turns)
    s = session_summary(ests)
    print(f"30-turn agent loop simulated:")
    print(f"  total tokens billed: {s['est_total_tokens']:,}")
    print(f"  history overhead share: {s['history_overhead_share']*100:.1f}%")
