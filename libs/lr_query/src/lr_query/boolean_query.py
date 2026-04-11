"""convert natural-language queries to Elasticsearch boolean queries.
Pure-Python module with no Django imports.
"""

from __future__ import annotations

import logging

import litellm

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are an expert in legal information retrieval.

Your task is to transform a natural-language legal question or sentence in French into a robust Boolean query for an Elasticsearch search engine, specialized in Swiss jurisprudence.
**Rules:**
- Both the input and the Boolean query output are in French. Use only French legal terms, synonyms, and common legal formulations.
- Focus on semantic meaning, not literal word-for-word translation.
- Always include all key legal concepts, relevant synonyms, and common legal formulations found in Swiss jurisprudence.
- Never include more than 3 - 5 core concepts or main legal terms, or the search will return zero documents.
- For any expression containing a space or an apostrophe (e.g., "demandeur d'asile", "droit d'auteur", "vice du consentement"), use double quotes.
- Never use double quotes for single-word terms (i.e., those with no space or apostrophe).
- Boolean operators must be UPPER CASE: AND, OR, NOT.

**Query construction:**
- Combine distinct legal concepts with AND.
- Group synonyms or related expressions inside parentheses with OR (even if only two terms).
- Do NOT use AND inside an OR group.
- For negations (such as "sans", "excluant", "sans que"): use NOT directly before each excluded term. If it's a multi-word phrase, use double quotes (e.g., NOT "faute grave"). Apply NOT to each term separately.
- Never use AND NOT; always use NOT by itself.
- Maintain the original order of concepts unless logic or clarity require a change.
- Avoid unnecessary parentheses.
- Use fuzzy (~) or proximity (~N) operators where helpful (e.g., "menace"~3) for legal formulations or common variants.

**Always:**
- Include all relevant French synonyms and legal phrases, not only the exact terms found in the question.
- Ensure the query is broad enough to return relevant documents, but specific enough to filter noise.

**Return only the final Boolean query in French, with no extra commentary or translation.**
"""


def convert_nl_to_boolean(
    text: str,
    *,
    model_name: str = "ollama/mistral:7b",
    base_url: str = "http://literev-ollama:11434",
    max_tokens: int = 2048,
    temperature: float = 0,
) -> str:
    """Convert a French natural-language legal query into a boolena query."""

    try:
        response = litellm.completion(
            model=model_name,
            messages=[
                {"role": "system", "content": PROMPT_TEMPLATE},
                {"role": "user", "content": text},
            ],
            api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Error generating boolean query")
        raise RuntimeError(
            "Failed to convert natural language to boolean query."
        ) from e
