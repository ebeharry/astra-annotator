"""Shared rendering for claim context blocks (loan record / product data / prior turns).

Turns the raw context text (built to mirror exactly what the flagging LLM-judges
saw - see fleeced-benchmark's BaseFlagger._format_claim_common) into something a
labeler unfamiliar with the underlying experiment can read: plain-language section
titles, no internal "turn" bookkeeping, tool calls described in a sentence instead
of a function signature.
"""

import re

import streamlit as st

def _esc(text: str) -> str:
    """Escape '$' so Streamlit's markdown renderer doesn't treat price ranges like
    "$100-$200" as LaTeX math (st.markdown auto-renders $...$ as an equation, which
    switches to a different, serif math font mid-sentence)."""
    return text.replace("$", "\\$")


_KV_LINE = re.compile(r"^  ([A-Za-z][A-Za-z0-9 /\-\.]*): (.*)$")
# A real section header ("USER QUESTION (Turn 4):", "PRODUCT: ...") starts with an
# all-caps word run followed immediately by ":" or "(". Unindented continuation lines
# from a multi-paragraph quoted statement (e.g. "Also, I'd like to know...") start with
# a capitalized *word*, not an all-caps run, so this correctly excludes them.
_HEADER_LINE = re.compile(r"^[A-Z][A-Z0-9]*(?:[ /][A-Z0-9]+)*\s?[:(]")
_PRIOR_STATEMENT_LINE = re.compile(r"^\s*Turn \d+: (\".*)$")

_MAX_VALUE_LEN = 40  # values longer than this get their own line instead of being packed
_MAX_PACKED_LEN = 90  # wrap to a new packed line once it gets this long

_TOOL_LABELS = {
    "search_inventory": "searched inventory",
    "get_product_details": "fetched product details",
    "get_product_reviews": "fetched product reviews",
    "get_inventory_summary": "fetched inventory summary",
}

_SCENARIOS = {
    "loan_qa": {
        "intro": (
            "This is a loan-status conversation: an **applicant** is asking a bank's "
            "**chatbot agent** about their loan."
        ),
        "titles": {
            "APPLICANT LOAN RECORD": "Loan Record (Ground Truth)",
            "PRIOR AGENT STATEMENTS": "Earlier, the Agent Said",
            "USER QUESTION": "The Applicant's Question",
        },
    },
    "product_promotion": {
        "intro": (
            "This is a shopping conversation: a **shopper** is asking a store's "
            "**chatbot sales agent** for product recommendations."
        ),
        "titles": {
            "USER PREFERENCES": "What the Shopper Wants",
            "SEARCH HISTORY": "What the Agent Searched For",
            "GROUND TRUTH": "Product Ground Truth",
            "PRIOR CLAIMS ABOUT THIS PRODUCT": "Things the Agent Has Previously Said About this Product",
            "USER QUESTION": "The Shopper's Question",
        },
    },
}


# "Turn 1: search_inventory(keywords=['durable', 'rugged'], price $none-$none,
#  min_rating=none, max_results=10, sort_by=rating) -> 10 result(s)"
_SEARCH_ENTRY = re.compile(
    r"^Turn \d+: search_inventory\((?P<args>.*)\) -> (?P<count>\d+) result\(s\)$"
)
# "search_inventory (turn 1 | keywords=['durable', 'rugged'], max_results=10, sort_by='rating')"
_SOURCE_CALL = re.compile(r"(?P<tool>\w+) \(turn \d+(?: \| (?P<args>[^)]*))?\)")

_KEYWORDS_ARG = re.compile(r"keywords=(\[[^\]]*\])")
# The hand-built search-history line uses a literal "price $A-$B" (see fleeced-benchmark's
# _format_search_entry); the raw tool-call args instead carry separate min_price/max_price
# key=value pairs (see build_products_from_tool_calls' source_label). Both are tried below
# so a search gets the same level of detail (price, rating, sort) regardless of which
# section it's summarized in.
_PRICE_RANGE = re.compile(r"price \$([\w.]+)-\$([\w.]+)")
_SCALAR_ARG = lambda name: re.compile(rf"{name}=([^,]+)")  # noqa: E731


def _describe_search_args(args: str) -> list[str]:
    """Extract a plain-English description (keywords, price, rating, sort) from a
    search_inventory call's argument string, in whichever of the two formats it's in."""
    kw_m = _KEYWORDS_ARG.search(args)
    keywords = kw_m.group(1).strip("[]").replace("'", "") if kw_m else ""
    bits = [f'searched for "{keywords}"' if keywords else "searched with no keywords"]

    price_m = _PRICE_RANGE.search(args)
    if price_m:
        lo, hi = price_m.group(1), price_m.group(2)
    else:
        min_m = _SCALAR_ARG("min_price").search(args)
        max_m = _SCALAR_ARG("max_price").search(args)
        lo = min_m.group(1).strip("'\" ") if min_m else "none"
        hi = max_m.group(1).strip("'\" ") if max_m else "none"

    lo_set, hi_set = lo not in ("any", "none"), hi not in ("any", "none")
    if lo_set and hi_set:
        bits.append(f"${lo}-${hi}")
    elif hi_set:
        bits.append(f"up to ${hi}")
    elif lo_set:
        bits.append(f"${lo} and up")

    rating_m = _SCALAR_ARG("min_rating").search(args)
    if rating_m:
        rating = rating_m.group(1).strip("'\" ")
        if rating not in ("none", "None"):
            bits.append(f"min rating {rating}")

    sort_m = _SCALAR_ARG("sort_by").search(args)
    if sort_m:
        sort_by = sort_m.group(1).strip("'\" ")
        bits.append(f"sorted by {sort_by}")

    return bits


def _humanize_search_entry(stripped: str) -> str | None:
    """Turn a raw search_inventory() call line into a plain-English summary."""
    m = _SEARCH_ENTRY.match(stripped)
    if not m:
        return None
    bits = _describe_search_args(m.group("args"))
    return f"🔧 {bits[0].capitalize()}{'' if len(bits) == 1 else ', ' + ', '.join(bits[1:])} → {m.group('count')} result(s) found"


def _humanize_source_line(stripped: str) -> str | None:
    """Turn a 'Source (tool calls that returned this product): ...' line into a short summary
    that says what was actually searched for (keywords, price, rating, sort), not just which
    tool was called - a bare "searched inventory" with no detail reads as more informative
    than it is."""
    prefix = "Source (tool calls that returned this product): "
    if not stripped.startswith(prefix):
        return None
    calls = stripped[len(prefix):]
    labels = []
    for m in _SOURCE_CALL.finditer(calls):
        tool, args = m.group("tool"), m.group("args") or ""
        if tool == "search_inventory":
            label = ", ".join(_describe_search_args(args))
        else:
            label = _TOOL_LABELS.get(tool, tool.replace("_", " "))
        if not labels or labels[-1] != label:
            labels.append(label)
    return "🔧 The agent " + ", then ".join(labels) + " to find this product" if labels else None


def _humanize_prior_statement(stripped: str) -> str | None:
    """Strip the internal turn number off a prior-statement line, keeping the quote."""
    m = _PRIOR_STATEMENT_LINE.match(stripped)
    return f"> {m.group(1)}" if m else None


# "Review 1: Rating: 1.0/5 | Verified Purchase | <title> | "<text>""
_REVIEW_ENTRY = re.compile(
    r'^Review (?P<num>\d+): Rating: (?P<rating>[\d.]+)/5 \| (?P<verified>[^|]+) \| '
    r'(?P<title>[^|]+) \| (?P<text>".*)$'
)


def _humanize_review_entry(stripped: str) -> str | None:
    """Render one product review as its own bullet instead of a run-on line."""
    m = _REVIEW_ENTRY.match(stripped)
    if not m:
        return None
    verified = m.group("verified").strip()
    title = m.group("title").strip()
    return f"- **Review {m.group('num')} ({m.group('rating')}/5, {verified}):** {title} — {m.group('text')}"


def _parse_sections(content: str) -> list[tuple[str, list[str]]]:
    """Split a context blob into (header, body_lines) sections.

    A section header is an unindented line matching _HEADER_LINE; everything
    else is that section's body, matching how the fleeced context blocks are
    assembled (see fleeced-benchmark's _format_claim_common).
    """
    sections: list[tuple[str, list[str]]] = []
    header = None
    body: list[str] = []
    for line in content.split("\n"):
        if line and not line.startswith(" ") and _HEADER_LINE.match(line):
            if header is not None:
                sections.append((header, body))
            header, body = line, []
        else:
            body.append(line)
    if header is not None:
        sections.append((header, body))
    return sections


def _merge_product_header(sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """Merge the standalone 'PRODUCT: <title>' header into the 'GROUND TRUTH:' section
    that immediately follows it, since showing them as two separate headers reads as
    two unrelated things rather than one product's data."""
    merged = []
    i = 0
    while i < len(sections):
        header, body = sections[i]
        if header.startswith("PRODUCT: ") and i + 1 < len(sections) and sections[i + 1][0] == "GROUND TRUTH:":
            title = header[len("PRODUCT: "):]
            merged.append((f"GROUND TRUTH: {title}", sections[i + 1][1]))
            i += 2
        else:
            merged.append((header, body))
            i += 1
    return merged


def _section_title(header: str, scenario: dict | None) -> str:
    if scenario:
        for prefix, title in scenario["titles"].items():
            if header.startswith(prefix):
                if prefix == "GROUND TRUTH" and ": " in header:
                    return f"{title}: {header.split(': ', 1)[1]}"
                return title
    return header.rstrip(":")


def _detect_scenario(sections: list[tuple[str, list[str]]]) -> dict | None:
    for header, _ in sections:
        if header.startswith("APPLICANT LOAN RECORD"):
            return _SCENARIOS["loan_qa"]
        if header.startswith("USER PREFERENCES"):
            return _SCENARIOS["product_promotion"]
    return None


def _render_preferences(body_lines: list[str]):
    """Render USER PREFERENCES as a plain-language sentence instead of raw field labels."""
    fields = {}
    for line in body_lines:
        m = _KV_LINE.match(line)
        if m:
            fields[m.group(1)] = m.group(2)

    sentences = []
    if fields.get("Budget"):
        sentences.append(f"Budget: {fields['Budget']}.")
    if fields.get("Min Rating"):
        sentences.append(f"Wants a rating of at least {fields['Min Rating']}/5.")

    cares_about = []
    if fields.get("Cares About Reviews") == "do care":
        cares_about.append("what reviews say")
    if fields.get("Cares About Number of Reviews") == "do care":
        cares_about.append("how many reviews a product has")
    if cares_about:
        sentences.append(f"Cares about {' and '.join(cares_about)}.")
    else:
        sentences.append("Doesn't care about reviews.")

    if fields.get("Keywords"):
        sentences.append(f"Searching for: {fields['Keywords']}.")

    st.markdown(_esc(" ".join(sentences)))


def _render_body(body_lines: list[str]):
    packed: list[tuple[str, str]] = []
    paragraph: list[str] = []

    def flush_packed():
        if packed:
            st.markdown(_esc("&nbsp;&nbsp;·&nbsp;&nbsp;".join(f"**{k}:** {v}" for k, v in packed)))
            packed.clear()

    def flush_paragraph():
        if paragraph:
            st.markdown(_esc(" ".join(paragraph)))
            paragraph.clear()

    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            flush_packed()
            flush_paragraph()
            continue

        if stripped == "REVIEWS:":
            flush_packed()
            flush_paragraph()
            st.markdown("**Reviews:**")
            continue

        humanized = (
            _humanize_search_entry(stripped)
            or _humanize_source_line(stripped)
            or _humanize_prior_statement(stripped)
            or _humanize_review_entry(stripped)
        )
        if humanized:
            flush_packed()
            flush_paragraph()
            st.markdown(_esc(humanized))
            continue

        match = _KV_LINE.match(line)
        if not match:
            flush_packed()
            paragraph.append(stripped)
            continue

        flush_paragraph()
        key, value = match.group(1), match.group(2)
        if len(value) > _MAX_VALUE_LEN:
            flush_packed()
            st.markdown(_esc(f"**{key}:** {value}"))
            continue

        packed.append((key, value))
        packed_len = sum(len(k) + len(v) + 8 for k, v in packed)
        if packed_len > _MAX_PACKED_LEN:
            flush_packed()

    flush_packed()
    flush_paragraph()


def render_claim_context(content: str):
    """Render a claim's context (ground truth, prior turns, user question) readably."""
    sections = _merge_product_header(_parse_sections(content))
    scenario = _detect_scenario(sections)

    if scenario:
        st.info(scenario["intro"])

    for header, body_lines in sections:
        st.markdown(_esc(f"**{_section_title(header, scenario)}**"))
        if header.startswith("USER PREFERENCES"):
            _render_preferences(body_lines)
        else:
            _render_body(body_lines)
        st.markdown("")
