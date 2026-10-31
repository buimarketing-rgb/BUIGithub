"""Prompt-injection defences for untrusted text (uploaded documents, web pages, user input).

Retrieved text is treated strictly as *data*. Lines that look like instructions aimed at the
model are neutralised before they reach the LLM, and the system prompt tells the model never to
follow instructions found inside sources.
"""
import re

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)",
    r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|system)",
    r"forget\s+(all\s+|everything|your)\s+(previous\s+)?(instructions|rules)?",
    r"you\s+are\s+now\s+(a|an|the)\b",
    r"new\s+(system\s+)?instructions?\s*:",
    r"(reveal|print|show|output)\s+(the\s+|your\s+)?(system\s+prompt|instructions|api[\s_-]?key|password|secret)",
    r"<\|?(im_start|im_end|system|endoftext)\|?>",
    r"^\s*(system|assistant)\s*:",
    r"\b(run|execute)\s+(this|the following)\s+(command|code|script)",
    r"act\s+as\s+(if\s+you\s+are\s+)?(an?\s+)?(unrestricted|jailbroken|dan)\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def contains_injection(text: str) -> bool:
    return bool(_INJECTION_RE.search(text or ""))


def sanitize_source_text(text: str) -> str:
    """Neutralises instruction-like lines in untrusted source text."""
    text = _CONTROL_RE.sub("", text or "")
    out = []
    for line in text.split("\n"):
        if _INJECTION_RE.search(line):
            out.append("[content removed by BUI: possible embedded instruction]")
        else:
            out.append(line)
    return "\n".join(out)


def clean_user_input(text: str, max_len: int = 4000) -> str:
    return _CONTROL_RE.sub("", text or "").strip()[:max_len]
