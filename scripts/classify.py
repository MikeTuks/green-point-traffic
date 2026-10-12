"""Keyword fallback for event category and size (PLAN.md, Classification rules)."""

# Checked in this order, so "Cycle Tour" is a race, not a concert.
CATEGORY_KEYWORDS = (
    ("race", ("marathon", "cycle tour", "half marathon", "10k", "fun run", "gun run")),
    ("parade", ("parade", "carnival", "pride", "tweede nuwe jaar")),
    ("sport", (" vs ", " v ", "stormers", "springboks", "svns", "sevens", "currie cup", "urc",
               "champions cup", "bafana")),
    ("concert", ("tour", "in concert", "festival", "calabash")),
)
BIG = ("springboks", "all blacks", "svns", "sevens", "marathon", "cycle tour", "gun run", "street parade")
SA_DERBY = ("bulls", "sharks", "lions")
SMALL = ("currie cup", "u20")


def category(name):
    """Category from keywords, or 'unknown'."""
    text = f" {name.lower()} "
    for cat, words in CATEGORY_KEYWORDS:
        if any(w in text for w in words):
            return cat
    return "unknown"


def size(cat, name, crowd=None):
    if crowd:
        return "small" if crowd < 15000 else "medium" if crowd <= 40000 else "big"
    text = name.lower()
    if cat == "concert" or any(w in text for w in BIG):
        return "big"
    if "stormers" in text and any(w in text for w in SA_DERBY):
        return "big"
    if any(w in text for w in SMALL):
        return "small"
    return "medium"
