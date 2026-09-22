"""
fact_types.py
-------------
Everything about classifying and formatting the three FactType values
(boolean, numeric, text). This module never talks to a model and never
verifies anything against a chunk - it only looks at a value in isolation
and says what kind of thing it is, whether it's a plausible value of a
given type, or how to render it back out.
"""


def classify_fact_type(value):
    """Guess whether a claimed value is boolean, numeric, or free text.
    Used only to label the ReaderResult - it never affects verification."""
    v = (value or "").strip().upper()
    if v in ("YES", "NO"):
        return "boolean"
    cleaned = v.replace("$", "").replace(",", "").strip()
    try:
        float(cleaned)
        return "numeric"
    except ValueError:
        return "text"


def is_valid_value(value, fact_type):
    """Check whether `value` is even the right *kind* of thing for
    `fact_type` ("boolean", "numeric", or "text"). Used to catch a model
    proposing a correction that doesn't match the fact's type at all -
    e.g. "corrected" a numeric fact to free text, or a YES/NO fact to a
    dollar amount. This never judges whether the value is factually
    correct, only whether it's a plausible value of that type."""
    v = (value or "").strip().upper()
    if not v:
        return False
    if fact_type == "boolean":
        return v in ("YES", "NO")
    if fact_type == "numeric":
        cleaned = v.replace("$", "").replace(",", "").strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    return True  # "text" facts accept any non-empty value


def format_amount(value):
    """Render a computed float back as a display string, e.g. 3250.0 -> '$3,250.00'."""
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return str(value)
