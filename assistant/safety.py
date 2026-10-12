import re
import logging

logger = logging.getLogger(__name__)

# Heuristic patterns identifying potential prompt injection in untrusted catalogue text or dealer input
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*prompt",
    r"\[system\]",
    r"admin\s+mode",
    r"you\s+must\s+(tell|say|confirm|create|give)",
    r"confirm\s+(the\s+)?(dealer's\s+)?order",
    r"create\s+(an\s+)?order\s+without",
    r"every\s+product\s+is\s+\d+%\s+off",
    r"vikmo-free-\d+",
    r"code\s+vikmo",
    r"forget\s+(all\s+)?(previous|your)\s+instructions",
    r"new\s+system\s+directive",
    r"developer\s+mode",
]

INJECTION_REGEX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def detect_prompt_injection(text: str) -> bool:
    """
    Returns True if the text contains heuristic patterns characteristic of
    prompt injection or unauthorized instruction overrides.
    """
    if not text:
        return False
    return bool(INJECTION_REGEX.search(text))


def sanitize_description(description: str, max_chars: int = 200) -> str:
    """
    Sanitize and truncate catalogue descriptions:
    1. Detect prompt injection; if found, withhold description.
    2. Strip control characters and collapse whitespace.
    3. Truncate safely to max_chars characters.
    """
    if not description:
        return ""

    if detect_prompt_injection(description):
        logger.warning("Prompt injection heuristic triggered on catalogue description. Withholding text.")
        return "[description withheld: contains instructions]"

    # Strip control characters except standard whitespace
    clean_text = "".join(ch for ch in description if ch.isprintable() or ch in " \t\n")
    # Collapse multiple whitespaces
    clean_text = " ".join(clean_text.split())

    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars].rstrip() + "..."

    return clean_text
