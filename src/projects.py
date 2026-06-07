"""
projects.py - Tag a Cowork session with the ZND project it belongs to.

Heuristics, in priority order:
1. Session cwd path ends with a known root suffix (hub detection).
2. Session cwd path component matching a known project folder name.
3. Session title keyword match.
4. First user message keyword match (when title is generic).

Returns (project_slug, confidence_0_to_1).
"""

from __future__ import annotations
import re
from typing import Tuple

PROJECT_PATTERNS = {
    "cipher":   [r"\bCIPHER\b", r"\bn8n\b", r"hetzner", r"meta resumable"],
    "jarvis":   [r"\bJARVIS\b", r"langgraph", r"local agent", r"voice agent",
                r"consulting work", r"time registration", r"time.entry"],
    "dsi":      [r"datastream", r"\bDSI\b", r"trade.flow", r"\bR1\b clearance"],
    "gha":      [r"github.actions", r"marketplace", r"billing app", r"zero-nonsense-dev"],
    "hub":      [r"ZeroNonsense\.dev", r"\bZND\b", r"\bhub\b",
                 r"company brief", r"portfolio\.md", r"DEADLINES\.md",
                 r"roadmap\.md", r"next_steps", r"SESSION_LOG"],
    "burnrate": [r"\bBurnRate\b", r"token.burn"],
    "work":     [r"a-insights", r"Fabric Warehouse", r"\bMedicare\b"],
}

CWD_PROJECT_MAP = {
    "cipher":                  "cipher",
    "jarvis":                  "jarvis",
    "datastream_intelligence": "dsi",
    "github-actions":          "gha",
    "zerononsense.dev":        "hub",
    "burnrate":                "burnrate",
    "work":                    "work",
}

# Root Cowork Output paths -> hub (cwd ENDS with these, case-insensitive, no trailing slash)
HUB_ROOT_SUFFIXES = [
    "claude cowork output",
    "claude cowork output\\zerononsense.dev",
    "claude cowork output/zerononsense.dev",
]


def tag_session(*, title, cwd, first_user_msg):
    """
    Returns (project_slug, confidence).

    confidence semantics:
      1.0  cwd path matched a known project subfolder
      0.9  cwd path ends with a known hub root suffix
      0.8  title contained a strong project keyword
      0.6  first user message contained a project keyword
      0.0  no match -> 'other'
    """
    title         = title or ""
    cwd           = cwd or ""
    first_user_msg= first_user_msg or ""

    cwd_lower = cwd.lower().rstrip("\\/")

    # 1a. Root Cowork Output folder -> hub
    for suffix in HUB_ROOT_SUFFIXES:
        if cwd_lower.endswith(suffix):
            return ("hub", 0.9)

    # 1b. Project subfolder match (inside path or at end)
    for folder_name, slug in CWD_PROJECT_MAP.items():
        if (f"\\{folder_name}\\" in cwd_lower or f"/{folder_name}/" in cwd_lower
                or cwd_lower.endswith(f"\\{folder_name}")
                or cwd_lower.endswith(f"/{folder_name}")):
            return (slug, 1.0)

    # 2. Title keyword match
    for slug, patterns in PROJECT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, title, re.IGNORECASE):
                return (slug, 0.8)

    # 3. First user message keyword match
    if first_user_msg:
        head = first_user_msg[:2000]
        for slug, patterns in PROJECT_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, head, re.IGNORECASE):
                    return (slug, 0.6)

    return ("other", 0.0)


if __name__ == "__main__":
    cases = [
        ("CIPHER project tasks (Cheaper)", "C:/.../local_xxx/outputs", "", "cipher"),
        ("JARVIS project (Cheaper)", "C:/.../local_yyy/outputs", "", "jarvis"),
        ("DataStream Intelligence project", "", "", "dsi"),
        ("ZeroNonsense.dev project", "", "", "hub"),
        ("Write work anniversary book message", "", "", "other"),
        ("Internal UI architecture", "", "design a CIPHER UI...", "cipher"),
        ("hub session", "C:\\Users\\WilcoDeTree\\OneDrive - Valona Intelligence\\Claude Cowork Output", "", "hub"),
        ("anything", "C:\\Users\\WilcoDeTree\\OneDrive - Valona Intelligence\\Claude Cowork Output\\CIPHER", "", "cipher"),
    ]
    for title, cwd, msg, expected in cases:
        slug, conf = tag_session(title=title, cwd=cwd, first_user_msg=msg)
        flag = "OK  " if slug == expected else "FAIL"
        print(f"{flag} title={title!r:55} -> {slug:8} conf={conf}")
