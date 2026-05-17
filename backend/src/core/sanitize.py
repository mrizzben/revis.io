"""Input sanitization utilities."""
import re


def sanitize_text(value: str) -> str:
    """Strip HTML tags and trim whitespace."""
    if not value:
        return value
    clean = re.sub(r"<[^>]*>", "", value)
    clean = re.sub(r"(?i)<script.*?>.*?</script>", "", clean)
    clean = re.sub(r"(?i)<style.*?>.*?</style>", "", clean)
    return clean.strip()
