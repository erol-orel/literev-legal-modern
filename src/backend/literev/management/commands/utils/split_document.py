import re

# ----------------------------
# Configuration
# ----------------------------

# Single-character sentinel (private-use area) to avoid regex pitfalls
DOT_SENTINEL = "\ue000"

# Abbreviations whose dot should NOT be treated as a sentence boundary
ABBREVIATIONS = [
    "art",
    "al",
    "ch",
    "let",
    "cf",
    "env",
    "etc",
    "ex",
    "vs",
    "p",
    "pp",
    "no",
    "n",
    "m",
    "me",
    "mme",
    "dr",
    "prof",
    "mr",
    "ms",
    "ing",
    "consid",
    "cst",
    "sj",
    "ss",
]

# Multi-dot abbreviations (optional but useful)
MULTI_DOT_ABBREVS = [
    r"\bp\.\s*ex\.",  # p. ex.
    r"\bc\.-à-d\.",  # c.-à-d.
]

# Major section headings that should behave like "hard boundaries"
# (kept uppercase on purpose to avoid splitting normal phrase "en fait")
SECTION_LINE_RE = re.compile(
    r"(?m)^\s*(EN\s+FAIT|EN\s+DROIT|EN\s+PROC[ÉE]DURE)\s*[:.]?\s*$"
)
PAR_CES_MOTIFS_RE = re.compile(r"(?m)^\s*(PAR\s+CES\s+MOTIFS\b.*)$")

# ----------------------------
# Helpers
# ----------------------------


def get_splitted_filename(
    record_key: str, decision_code: str, index_name: str
) -> str:
    "Return the name of the splitted document."
    return (
        f"{record_key}__{decision_code}__{index_name}_splitted.json".replace(
            "/", "_"
        )
    )


def get_classified_filename(
    record_key: str, decision_code: str, index_name: str
) -> str:
    "Return the name of the classified document."
    return (
        f"{record_key}__{decision_code}__{index_name}_classified.json".replace(
            "/", "_"
        )
    )


def _protect_dots_in_match(m: re.Match) -> str:
    "Replace every '.' inside the matched string with DOT_SENTINEL."
    return m.group(0).replace(".", DOT_SENTINEL)


def _is_heading_start(s: str) -> bool:
    "Return True if the string begins with a major section heading otherwise else."
    return bool(
        re.match(
            r'^\s*["\u00ab(\[]*(?:EN\s+FAIT|EN\s+DROIT|EN\s+PROC[ÉE]DURE|PAR\s+CES\s+MOTIFS)\b',
            s,
        )
    )


def _normalize_linebreaks(text: str) -> str:
    """
    Normalize line endings.

    Preserve paragraph breaks (blank lines)
    Preserve bullet/list item breaks as paragraph breaks
    Force paragraph boundaries around major section headings
    Convert remaining single newlines (soft wraps) into spaces
    """
    text = re.sub(r"[\u00a0\t]", " ", text)
    text = re.sub(r"\r\n?", "\n", text)

    # Force paragraph breaks around major headings BEFORE collapsing single newlines
    text = SECTION_LINE_RE.sub(lambda m: f"\n\n{m.group(1)}\n\n", text)
    text = PAR_CES_MOTIFS_RE.sub(lambda m: f"\n\n{m.group(1)}\n\n", text)

    # Normalize multi blank lines to a paragraph break marker (\n\n)
    text = re.sub(r"\n{2,}", "\n\n", text)

    # Treat bullet/list item starts as paragraph boundaries
    # Examples: "-", "•", "1.", "1)", "(1)" at line start
    text = re.sub(r"\n(?=\s*(?:[-•\u2022]|\(?\d{1,3}\)?[.)]))", "\n\n", text)

    # Convert remaining single newlines to spaces (PDF soft wraps)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # If extraction produced ".... EN FAIT" inline, force a paragraph break (uppercase headings only)
    text = re.sub(
        r"([.?!…])\s+(EN\s+FAIT|EN\s+DROIT|EN\s+PROC[ÉE]DURE|PAR\s+CES\s+MOTIFS)\b",
        r"\1\n\n\2",
        text,
    )

    # Collapse excessive spaces + normalize paragraph breaks
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_blocks(text: str) -> list[str]:
    """
    Split text into blocks at paragraph breaks that introduce major headings.

    This lets us split BEFORE headings even if the previous block has no punctuation (typical header).
    """
    blocks = re.split(
        r"\n\n(?=\s*(?:EN\s+FAIT|EN\s+DROIT|EN\s+PROC[ÉE]DURE|PAR\s+CES\s+MOTIFS)\b)",
        text,
    )
    return [b.strip() for b in blocks if b.strip()]


# ----------------------------
# Core logic
# ----------------------------


def legal_sentence_split(text: str) -> list[str]:
    "Split the document into valid legal sentences."
    text = _normalize_linebreaks(text)

    # Protect abbreviation dots (e.g., "art.", "Mme.")
    abbrevs_sorted = sorted(ABBREVIATIONS, key=len, reverse=True)
    abbrev_re = re.compile(
        r"\b(?:" + "|".join(map(re.escape, abbrevs_sorted)) + r")\.",
        re.IGNORECASE,
    )
    text = abbrev_re.sub(lambda m: m.group(0)[:-1] + DOT_SENTINEL, text)

    # Protect common initialisms like "U.S.A." or "S.A."
    text = re.sub(r"\b(?:[A-Z]\.){2,}", _protect_dots_in_match, text)

    # Protect dates "dd.mm.yyyy" and decimals "3.14"
    text = re.sub(
        r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", _protect_dots_in_match, text
    )
    text = re.sub(r"\b\d+\.\d+\b", _protect_dots_in_match, text)

    # Protect a few multi-dot abbreviations
    for pat in MULTI_DOT_ABBREVS:
        text = re.sub(pat, _protect_dots_in_match, text, flags=re.IGNORECASE)

    # Protect legal enumerations where authors often write a trailing dot after the number:
    # "art. 24." / "ch. 1." / "al. 2." / "let. b."
    text = re.sub(
        r"(\b(?:art|ch|al|let)"
        + re.escape(DOT_SENTINEL)
        + r"\s*[\d]+(?:\s*[a-z])?)\.",
        lambda m: m.group(1) + DOT_SENTINEL,
        text,
        flags=re.IGNORECASE,
    )

    # NEW: Protect lettered list markers that otherwise become tiny sentences, e.g. "8) a." or paragraph-start "a."
    text = re.sub(
        r"(\b\d{1,3}\)\s*[a-z])\.", lambda m: m.group(1) + DOT_SENTINEL, text
    )
    text = re.sub(
        r"(^|\n\n)(\s*)([a-z])\.",
        lambda m: m.group(1) + m.group(2) + m.group(3) + DOT_SENTINEL,
        text,
    )

    # Sentence splitting
    sentence_re = re.compile(
        r"""
        (.*?                                   # minimal content
           (?:\.\.\.|[!?…]|[.])                # sentence end punctuation
           [)"\]\u00bb]*                       # optional closing quotes/brackets (», ], ", ))
        )
        (?=
            \n\n                                # paragraph break
            |
            \s+["\u00ab(\[]*[A-ZÉÈÀÂÎÔÛÄËÏÖÜÇ0-9]  # next sentence likely starts
            |
            $                                   # end
        )
        """,
        re.VERBOSE | re.DOTALL,
    )

    sentences: list[str] = []

    # Block-wise split (ensures we can cut before headings even without punctuation)
    for block in _split_into_blocks(text):
        matches = [
            m.group(1).strip()
            for m in sentence_re.finditer(block)
            if m.group(1).strip()
        ]
        if matches:
            sentences.extend(matches)
        else:
            # Fallback: block with no terminal punctuation (common for headers)
            sentences.append(block.strip())

    # Restore protected dots
    sentences = [s.replace(DOT_SENTINEL, ".").strip() for s in sentences]
    return [s for s in sentences if s]


def merge_short_sentences(
    sentences: list[str],
    min_chars: int = 60,
    min_words: int = 8,
    max_chars: int = 600,
) -> list[str]:
    """
    Merge adjacent segments until they reach a minimum size.

    Uses both word and character thresholds.
    Avoids merging across major headings (EN FAIT, EN DROIT, PAR CES MOTIFS, …).
    Caps merges to avoid producing extremely long outputs.
    """
    out: list[str] = []
    buf = ""

    def small(s: str) -> bool:
        return (len(s) < min_chars) or (len(s.split()) < min_words)

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        if not buf:
            buf = s
            continue

        # Do not merge across major section headings
        if _is_heading_start(s) and not _is_heading_start(buf):
            out.append(buf)
            buf = s
            continue

        should_merge = small(buf) or buf.endswith((":", ";", ","))

        if should_merge and (len(buf) + 1 + len(s) <= max_chars):
            buf = f"{buf} {s}"
        else:
            out.append(buf)
            buf = s

    if buf:
        # Merge trailing short segment into previous one when feasible (but not if it's a heading)
        if (
            out
            and small(buf)
            and (len(out[-1]) + 1 + len(buf) <= max_chars)
            and not _is_heading_start(buf)
        ):
            out[-1] = f"{out[-1]} {buf}"
        else:
            out.append(buf)

    return out
