"""Extract and classify French legal text into 'mineure' and 'majeure'."""

from __future__ import annotations

import json
import logging
import random
import re
import time

from typing import Any, Callable, Optional, Tuple

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger("__name__")
logger.setLevel(logging.INFO)

DOT = "⟂"
ABBR = r"(?:art|al|let|consid|cf|n|no|n°|ch|p|etc)"
ABBR_DOT = re.compile(rf"\b({ABBR})\.", re.IGNORECASE)
DOTTED_NUM = re.compile(r"(?<=\d)\.(?=\d)")
PARENS = re.compile(r"\((.*?)\)", re.DOTALL)
SPLIT_RE = re.compile(r"([.!?]+)(?=(?:\s+)(?:[A-ZÉÈÊÀÂÎÔÛÄËÏÖÜÇ0-9'»\(\[]))")


try:
    from ftfy import fix_text as _ftfy
except Exception:
    _ftfy = None


def _fix_mojibake(s: str) -> str:
    """Best-effort encoding repair; uses ftfy if available."""
    if _ftfy:
        return _ftfy(s)
    rep = {
        # RIGHT SINGLE QUOTATION MARK
        "\u00e2\u0080\u0099": "\u2019",
        # EN DASH
        "\u00e2\u0080\u0093": "\u2013",
        # EM DASH
        "\u00e2\u0080\u0094": "\u2014",
        # LEFT DOUBLE QUOTATION MARK
        "\u00e2\u0080\u009c": "\u201c",
        # RIGHT DOUBLE QUOTATION MARK
        "\u00e2\u0080\u009d": "\u201d",
        # Latin-1 decoded UTF-8 sequences for French letters
        "\u00c3\u00a9": "\u00e9",  # e acute
        "\u00c3\u00a8": "\u00e8",  # e grave
        "\u00c3\u00aa": "\u00ea",  # e circumflex
        "\u00c3\u00ab": "\u00eb",  # e diaeresis
        "\u00c3": "\u00e0",  # a grave (common collapsed form)
        "\u00c3\u00a2": "\u00e2",  # a circumflex
        "\u00c3\u00a7": "\u00e7",  # c cedilla
        "\u00c3\u00ae": "\u00ee",  # i circumflex
        "\u00c3\u00b4": "\u00f4",  # o circumflex
        "\u00c3\u00bb": "\u00fb",  # u circumflex
        "\u00c3\u00bc": "\u00fc",  # u diaeresis
        "\u00c3\u00b6": "\u00f6",  # o diaeresis
    }
    for k, v in rep.items():
        s = s.replace(k, v)
    return s


def normalize_text(raw: str) -> str:
    """Clean and merge fragmented lines before sentence chunking."""
    s = raw or ""
    s = (
        s.replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = _fix_mojibake(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s).strip()

    lines = s.splitlines()
    merged: list[str] = []
    # Accept ASCII ), ", right guillemet, right single quote (via escapes)
    terminal_rx = re.compile(r'[.!?:;)"\u00BB\u2019]\s*$')

    for line in lines:
        if merged and not terminal_rx.search(merged[-1]):
            merged[-1] = f"{merged[-1]} {line.strip()}"
        else:
            merged.append(line.strip())

    s = " ".join(merged)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _shield(t: str) -> str:
    """Protect dots inside abbreviations, numbers, and parentheses."""
    t = ABBR_DOT.sub(lambda m: m.group(1) + DOT, t)

    def _paren_sub(m: re.Match) -> str:
        inner = m.group(1)
        inner = re.sub(r"\.\s", DOT + " ", inner)
        inner = inner.replace("..", DOT + DOT).replace(".;", DOT + ";")
        return f"({inner})"

    t = PARENS.sub(_paren_sub, t)
    t = DOTTED_NUM.sub(DOT, t)
    return t


def _unshield(t: str) -> str:
    """Restore protected dots."""
    return t.replace(DOT, ".")


def split_sentences_fr_legal(text: str) -> list[str]:
    """Split French legal text into sentences.

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    list[str]
        Sentence list tailored for legal text.
    """
    s = _shield(text)
    parts, last = [], 0
    for m in SPLIT_RE.finditer(s):
        end = m.end(1)
        seg = s[last:end].strip()
        if seg:
            parts.append(seg)
        last = end
    tail = s[last:].strip()
    if tail:
        parts.append(tail)
    parts = [_unshield(p) for p in parts if p.strip()]

    repaired: list[str] = []
    for p in parts:
        if repaired:
            prev = repaired[-1]
            if re.match(r"^[a-zà-ÿ“”\"'»\)\];,:-]", p):
                repaired[-1] = prev + " " + p
                continue
            if re.search(r"[;,]$", prev):
                repaired[-1] = prev + " " + p
                continue
            if re.fullmatch(r"\d+\.", prev) and re.match(r"^\d+\.\d+", p):
                repaired[-1] = prev + " " + p
                continue
        repaired.append(p)

    merged: list[str] = []
    for seg in repaired:
        is_short_paren = re.fullmatch(r"\([\s\S]{0,160}\)?\.?", seg)
        if (
            merged
            and is_short_paren
            and re.search(
                r"\bart\b|\bATF\b|\bACJC\b|\bCPC\b|\bCC\b|\bLTF\b",
                seg,
                re.IGNORECASE,
            )
        ):
            merged[-1] = merged[-1].rstrip() + " " + seg
        else:
            merged.append(seg)

    out = []
    i = 0
    while i < len(merged):
        cur = merged[i]
        if re.fullmatch(r"['\"]?\d+(?:\.\d+)*\.", cur) and i + 1 < len(merged):
            out.append(cur + " " + merged[i + 1])
            i += 2
        else:
            out.append(cur)
            i += 1
    return out


_ENC: Any = None
try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def _tlen(x: str) -> int:
        return len(_ENC.encode(x))

    def _tail_tokens(txt: str, keep: int) -> str:
        ids = _ENC.encode(txt)
        keep = max(0, len(ids) - keep)
        return _ENC.decode(ids[keep:])
except Exception:  # pragma: no cover - optional dependency

    def _tlen(x: str) -> int:
        return max(1, len(x) // 4)

    def _tail_tokens(txt: str, keep: int) -> str:
        return txt[-keep * 4 :]


def pack_chunks(
    sents: list[str],
    max_tokens: int = 900,
    overlap_tokens: int = 80,
    min_sent_tokens: int = 5,
) -> list[str]:
    """Pack sentences into token-limited chunks with optional overlap.

    Parameters
    ----------
    sents : list[str]
        Sentence list.
    max_tokens : int, default 900
        Max tokens per chunk.
    overlap_tokens : int, default 80
        Overlap tokens from previous chunk tail.
    min_sent_tokens : int, default 5
        If a sentence is very short, merge with next.

    Returns
    -------
    list[str]
        Packed chunks.
    """
    chunks: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    i = 0
    while i < len(sents):
        s = (sents[i] or "").strip()
        if not s:
            i += 1
            continue
        if _tlen(s) < min_sent_tokens and i + 1 < len(sents):
            s = s + " " + sents[i + 1]
            i += 1
        sl = _tlen(s)
        if sl > max_tokens:
            # hard wrap long sentence
            words = s.split(" ")
            buf: list[str] = []
            bt = 0
            for w in words:
                add = (" " if buf else "") + w
                wt = _tlen(add)
                if bt + wt > max_tokens:
                    chunks.append("".join(buf))
                    buf = [w]
                    bt = _tlen(w)
                else:
                    buf.append(add)
                    bt += wt
            if buf:
                chunks.append("".join(buf))
            i += 1
            continue
        if cur_tok + sl <= max_tokens:
            cur.append(s)
            cur_tok += sl
            i += 1
        else:
            if cur:
                chunks.append(" ".join(cur).strip())
            if overlap_tokens and chunks:
                ov = _tail_tokens(chunks[-1], overlap_tokens)
                cur = [ov] if ov else []
                cur_tok = _tlen(ov) if ov else 0
            else:
                cur = []
                cur_tok = 0
    if cur:
        chunks.append(" ".join(cur).strip())
    return [c for c in chunks if c]


class Classification(BaseModel):
    """Pydantic model for classification result."""

    majeure: list[str]
    mineure: list[str]


def expected_ids(n: int) -> list[str]:
    """Return expected CHUNK_i identifiers for n chunks."""
    return [f"CHUNK_{i}" for i in range(n)]


def validate_classification(n: int, c: Classification) -> Tuple[bool, str]:
    """Validate classification against expected IDs.

    Parameters
    ----------
    n : int
        Number of chunks.
    c : Classification
        Classification result.

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message)
    """
    exp = set(expected_ids(n))
    got = set(c.majeure) | set(c.mineure)
    errs = []
    unknown = got - exp
    if unknown:
        errs.append(f"Unknown IDs: {sorted(unknown)}")
    missing = exp - got
    if missing:
        errs.append(f"Missing IDs: {sorted(missing)}")
    both = set(c.majeure) & set(c.mineure)
    if both:
        errs.append(f"IDs in both categories: {sorted(both)}")
    return (len(errs) == 0, "; ".join(errs))


SYSTEM_PROMPT = (
    "Tu es juriste. On te fournit des 'chunks' numérotés (CHUNK_i) d'un "
    "arrêt. Classe CHAQUE chunk en exactement UNE catégorie:\n"
    "- Majeure: règle de droit générale/applicable (loi, règlement, "
    "jurisprudence, standard, test, compétence, recevabilité).\n"
    "- Mineure: faits/circonstances de l'espèce, application de la règle "
    "aux faits, procédure concrète, montants/dates.\n"
    "Contraintes STRICTES:\n"
    '1) Sors UNIQUEMENT un JSON UTF-8 de la forme EXACTE: {"majeure": '
    '[...], "mineure": [...]} \n'
    '2) Utilise les clés au SINGULIER: "majeure" et "mineure".\n'
    "3) Chaque ID CHUNK_i apparaît UNE seule fois.\n"
    "4) N'invente pas d'IDs, n'ajoute aucun commentaire.\n"
    "Ambigu: fonction dominante; hésitation -> 'majeure' si une norme/"
    "standard clair est énoncé, sinon 'mineure'."
)


def _dbg_preview(s: Optional[str], n: int = 400) -> str:
    """Preview head/tail of a long string for logging."""
    if s is None:
        return "None"
    s = str(s)
    return (s[:n] + " …[truncated]… " + s[-n:]) if len(s) > 2 * n else s


def build_user_prompt(chunks: list[str]) -> str:
    """Build the user prompt listing all chunk IDs and text.

    Parameters
    ----------
    chunks : list[str]
        Chunk texts.

    Returns
    -------
    str
        Prompt string.
    """
    n = len(chunks)
    lines = [
        "Texte à classifier (ne pas modifier le texte). "
        f"N={n}. IDs valides: CHUNK_0 à CHUNK_{n - 1}. "
        f"Tu dois renvoyer exactement {n} IDs au total "
        f"(majeure + mineure = {n}). Les SEULES clés autorisées sont "
        "«majeure» et «mineure». Chaque ID apparaît une seule fois au "
        "format exact «CHUNK_i» (chaîne)."
    ]
    for i, t in enumerate(chunks):
        lines.append(f"\nCHUNK_{i}:\n«{t}»")
    lines.append("\nRéponds UNIQUEMENT par le JSON demandé.")
    return "\n".join(lines)


_openai_client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", ""))


def openai_llm_call(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    json_only: bool = True,
    retries: int = 1,
    base_backoff: float = 0.8,
) -> str:
    """Call OpenAI Chat Completions with optional JSON mode.

    Parameters
    ----------
    system_prompt : str
        System message content.
    user_prompt : str
        User message content.
    model : str, default "gpt-4.1-mini"
        Model name.
    temperature : float, default 0.0
        Sampling temperature.
    max_tokens : int or None, optional
        Max output tokens.
    json_only : bool, default True
        If True, request JSON object format.
    retries : int, default 1
        Retry attempts on error.
    base_backoff : float, default 0.8
        Base backoff for retries.

    Returns
    -------
    str
        Model response text.
    """
    for attempt in range(retries + 1):
        try:
            kwargs: dict = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            if json_only:
                kwargs["response_format"] = {"type": "json_object"}
            resp = _openai_client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            if attempt >= retries:
                raise
            sleep_s = (
                base_backoff * (2**attempt) * (1 + 0.25 * random.random())
            )
            logger.debug(
                f"[LLM] retry {attempt + 1}/{retries} after error: {e} (sleep={sleep_s:.2f}s)",
            )
            time.sleep(sleep_s)

    raise RuntimeError("OpenAI call exhausted retries without a response.")


def _normalize_classif_payload(n: int, data: dict) -> dict:
    """Normalize raw model JSON keys and coerce items to CHUNK_i strings.

    Parameters
    ----------
    n : int
        Number of chunks (unused here, kept for compatibility).
    data : dict
        Raw JSON loaded from the model.

    Returns
    -------
    dict
        Normalized payload with "majeure"/"mineure" keys.
    """
    key_map = {
        "majeures": "majeure",
        "maj": "majeure",
        "majors": "majeure",
        "mineures": "mineure",
        "min": "mineure",
        "minors": "mineure",
    }
    fixed: dict = {}
    for k, v in data.items():
        kk = key_map.get(k.strip().lower(), k.strip().lower())
        fixed[kk] = v

    def coerce(arr: list | None) -> list[str]:
        out: list[str] = []
        for x in arr or []:
            if isinstance(x, int) or (isinstance(x, str) and x.isdigit()):
                x = f"CHUNK_{int(x)}"
            elif (
                isinstance(x, str)
                and not x.startswith("CHUNK_")
                and x.replace("CHUNK", "").strip().isdigit()
            ):
                x = "CHUNK_" + re.sub(r"\D+", "", x)
            out.append(str(x))
        return out

    if "majeure" in fixed:
        fixed["majeure"] = coerce(fixed["majeure"])
    if "mineure" in fixed:
        fixed["mineure"] = coerce(fixed["mineure"])
    return fixed


_CHUNK_RX = re.compile(r"^CHUNK_(\d+)$")


def _ids_to_indices(ids: list[str]) -> list[int]:
    """Convert CHUNK_i strings to integer indices."""
    out: list[int] = []
    for cid in ids:
        m = _CHUNK_RX.match(cid)
        if not m:
            raise ValueError(f"Invalid ID: {cid!r}")
        out.append(int(m.group(1)))
    return out


def materialize_classification(
    result: Classification,
    chunks: list[str],
    order: str = "document",
) -> Tuple[list[str], list[str]]:
    """Map classified IDs back to chunk texts.

    Parameters
    ----------
    result : Classification
        Classification with CHUNK_i IDs.
    chunks : list[str]
        Source chunk texts.
    order : str, default "document"
        "document": sort indices ascending; "model": keep model order.

    Returns
    -------
    tuple[list[str], list[str]]
        (majeure_texts, mineure_texts)
    """
    maj_idx = _ids_to_indices(result.majeure)
    min_idx = _ids_to_indices(result.mineure)
    if order == "document":
        maj_idx.sort()
        min_idx.sort()
    elif order != "model":
        raise ValueError("order must be 'document' or 'model'")
    n = len(chunks)
    for i in maj_idx + min_idx:
        if not (0 <= i < n):
            raise IndexError(f"Index out of bounds: {i} (0..{n - 1})")
    return [chunks[i] for i in maj_idx], [chunks[i] for i in min_idx]


def classify_chunks_llm(
    chunks: list[str],
    llm_call: Callable[[str, str], str],
) -> Classification:
    """Single-shot classification with set-based validation and fixes.

    Policy
    ------
    - Unknown IDs: drop (log).
    - Overlap: keep only in mineure (remove from majeure).
    - Missing: append to mineure (log).

    Parameters
    ----------
    chunks : list[str]
        Chunk texts.
    llm_call : Callable[[str, str], str]
        LLM calling function (system, user) -> str.

    Returns
    -------
    Classification
        Cleaned classification result.
    """
    sys_p = SYSTEM_PROMPT
    usr_p = build_user_prompt(chunks)

    logger.debug(
        f"[MM] classify_chunks_llm: n_chunks={len(chunks)}, approx_chars={sum(len(c) for c in chunks)}"
    )
    logger.debug(
        f"[MM] attempt 1/1 — sending prompt with {len(chunks)} CHUNKs"
    )

    raw = llm_call(sys_p, usr_p) or ""
    raw = raw.strip()

    logger.debug(f"[MM] attempt 1 — raw_len={len(raw)}")
    logger.debug(f"[MM] attempt 1 — raw_head_tail={_dbg_preview(raw, 500)}")

    m = re.search(r"\{[\s\S]*\}\s*$", raw)
    body = m.group(0) if m else raw
    if not m:
        logger.debug(
            "[MM] attempt 1 — no trailing JSON braces found; using full raw"
        )

    try:
        data = json.loads(body)
    except Exception as e:
        logger.debug(f"[MM][PARSE] attempt 1 — exception={e!r}")
        logger.debug(
            f"[MM][PARSE] attempt 1 — body_head_tail={_dbg_preview(body, 500)}"
        )
        raise ValueError(f"Invalid classification JSON: {e}")

    data = _normalize_classif_payload(len(chunks), data)
    logger.debug(
        f"[MM] attempt 1 — parsed JSON keys={sorted(list(data.keys()))}",
    )

    if ("majeures" in data) or ("mineures" in data):
        logger.debug(
            f"[MM][WARN] plural keys detected (expected 'majeure'/'mineure'): {sorted(list(data.keys()))}",
            sorted(list(data.keys())),
        )

    maj_raw = {s for s in (data.get("majeure") or []) if _CHUNK_RX.match(s)}
    min_raw = {s for s in (data.get("mineure") or []) if _CHUNK_RX.match(s)}

    expected = set(expected_ids(len(chunks)))
    got = maj_raw | min_raw

    unknown = got - expected
    missing = expected - got
    overlap = maj_raw & min_raw

    if unknown:
        logger.debug(
            f"[MM][VALIDATOR] unknown={len(unknown)} sample={list(unknown)[:10]}",
        )
        maj_raw -= unknown
        min_raw -= unknown

    if overlap:
        logger.debug(
            f"[MM][VALIDATOR] both={len(overlap)} sample={list(overlap)[:10]}",
        )
        maj_raw -= overlap
        min_raw |= overlap

    if missing:
        logger.debug(
            f"[MM][VALIDATOR] missing={len(missing)} sample={list(missing)[:10]}",
        )
        min_raw |= missing

    logger.debug(
        f"[MM] VALID (set-policy). majeure={len(maj_raw)} mineure={len(min_raw)}",
    )
    return Classification(majeure=list(maj_raw), mineure=list(min_raw))


def get_sentences(text: str) -> list[str]:
    """
    Split a French legal text into sentences while protecting periods that
    should not trigger a split (abbreviations, enumerations, decimals).

    Parameters
    ----------
    text : str
        Input text.

    Returns
    -------
    list[str]
        Sentence-like segments.
    """
    legal_abbreviations = [
        "art",
        "Art",
        "al",
        "alinéa",
        "par",
        "§",
        "M",
        "Mme",
        "Mlle",
        "Dr",
        "Pr",
        "Av",
        "Not",
        "Mgr",
        "Me",
        "St",
        "etc",
        "cf",
        "ex",
        "i.e",
        "e.g",
        "op.cit",
        "loc.cit",
        "c.c",
        "c.p",
        "c.trav",
        "c.comm",
        "c.consom",
        "c.pen",
        "C.deC",
        "C.fam",
        "No",
        "n°",
        "vol",
        "fig",
        "p",
        "pp",
        "éd",
    ]

    PLACEHOLDER = "\ue000"

    escaped_abbrs = [re.escape(a) for a in legal_abbreviations]
    abbr_regex = re.compile(
        r"\b(?:" + "|".join(escaped_abbrs) + r")\.", flags=re.UNICODE
    )

    enum_multilevel_trailing = re.compile(r"\b(\d+(?:\.\d+)+)\.(?=\s|$)")
    enum_single_trailing = re.compile(r"\b(\d+)\.(?=\s+[A-ZÀ-ÖØ-Ý])")
    decimal_or_internal = re.compile(r"(?<=\d)\.(?=\d)")

    def protect(text: str) -> str:
        text = abbr_regex.sub(lambda m: m.group(0)[:-1] + PLACEHOLDER, text)
        text = enum_multilevel_trailing.sub(
            lambda m: m.group(1) + PLACEHOLDER, text
        )
        text = enum_single_trailing.sub(
            lambda m: m.group(1) + PLACEHOLDER, text
        )
        text = decimal_or_internal.sub(PLACEHOLDER, text)
        return text

    def unprotect(text: str) -> str:
        return text.replace(PLACEHOLDER, ".")

    protected_text = protect(text)

    pattern = r"(?<=[.?!])\s+(?=[A-ZÀ-ÖØ-Ý])|\n+"
    sentences = [
        unprotect(s.strip())
        for s in re.split(pattern, protected_text.strip())
        if s.strip()
    ]

    return sentences
