"""
fact_types.py
-------------
Everything about classifying and formatting the three FactType values
(boolean, numeric, text). This module never talks to a model and never
verifies anything against a chunk - it only looks at a value in isolation
and says what kind of thing it is, whether it's a plausible value of a
given type, or how to render it back out.
"""
import re
from datetime import datetime

_BOOLEAN_TRUE = {"YES", "Y", "TRUE"}
_BOOLEAN_FALSE = {"NO", "N", "FALSE"}
_UNKNOWN_TOKENS = {"N/A", "NA", "NONE", "UNKNOWN", "-", ""}
 
# Wrapper pairs to strip before classification, e.g. "<4200>" -> "4200"
_WRAPPERS = [("<", ">"), ("[", "]"), ("(", ")"), ('"', '"'), ("'", "'")]
 
# Leading hedge words that don't change the underlying type, e.g.
# "approximately 4200" -> "4200"
_QUALIFIER_RE = re.compile(
    r"^(approximately|approx\.?|about|around|roughly|~)\s+", re.IGNORECASE
)
 
_PERCENT_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?\s*%$")
 
_DATE_FORMATS = (
    "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y",
    "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
)
 
 
def _strip_wrappers(value):
    """Remove one layer of enclosing brackets/quotes and any leading hedge word."""
    v = value.strip()
    for open_c, close_c in _WRAPPERS:
        if len(v) >= 2 and v.startswith(open_c) and v.endswith(close_c):
            v = v[1:-1].strip()
    return _QUALIFIER_RE.sub("", v).strip()
 
 
def _to_float(s):
    try:
        return float(s)
    except ValueError:
        return None
 
 
def _looks_like_date(s):
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False
 
 
def classify_fact_type(value):
    """Guess whether a claimed value is boolean, currency, percent, numeric,
    date, unknown, or plain text. Used only to label the ReaderResult - it
    never affects verification.
    """
    if value is None:
        return "unknown"
 
    raw = _strip_wrappers(str(value))
    if not raw:
        return "unknown"
 
    upper = raw.upper()
    if upper in _UNKNOWN_TOKENS:
        return "unknown"
    if upper in _BOOLEAN_TRUE or upper in _BOOLEAN_FALSE:
        return "boolean"
    if _PERCENT_RE.match(raw.replace(" ", "")):
        return "percent"
    # As is, this will only sometimes catch a numeric currency.
    # this needs more context, it's relying on the model putting $ in the number, 
    # but it can do <4,250> while still referring to a currency. 
    is_currency = raw.startswith(("$", "+$", "-$")) 
    numeric_candidate = raw.replace("$", "").replace(",", "").strip()
    if _to_float(numeric_candidate) is not None:
        return "currency" if is_currency else "numeric"
 
    if _looks_like_date(raw):
        return "date"
 
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
