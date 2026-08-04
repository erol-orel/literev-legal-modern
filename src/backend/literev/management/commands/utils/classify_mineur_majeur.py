import json
import logging

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger("minuer majeur classify")
logger.setLevel(logging.DEBUG)

CHAT_MODEL = "gpt-4.1-mini"

# Built lazily: the openai SDK raises when constructed without an API key, so
# eager construction made importing this module require OPENAI_API_KEY.
_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=getattr(settings, "OPENAI_API_KEY", "")
        )
    return _openai_client


def get_filename(doc_id: str, decision_code: str, index_name: str) -> str:
    return f"{doc_id}__{decision_code}__{index_name}_structured.json".replace(
        "/", "_"
    )


def classify_decision(decision_text: str):
    # First call: segmentation (plain text, no JSON)
    segmentation_prompt = f"""
    Segment the following Swiss judicial decision into these sections:
    - Metadata
    - Majeure
    - Mineure-Faits
    - Mineure-Subsommation
    - Conclusion

    Do NOT output JSON. Just structure the text clearly under each heading.

    Decision:
    {decision_text}
    """

    seg_response = _get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": segmentation_prompt}],
        temperature=0,
    )

    if not seg_response.choices[0].message.content:
        return ""

    seg = seg_response.choices[0].message.content.strip()

    # Second call: JSON structuring
    classification_prompt = f"""
    Convert the following segmented judicial decision into valid JSON with exactly these keys:
    - Metadata
    - Majeure
    - Mineure-Faits
    - Mineure-Subsommation
    - Conclusion

    Output format must be a valid JSON object.
    Each value must be a list of text fragments (strings).
    If a category is empty, use an empty list [].
    Do not output explanations, comments, or text outside the JSON.

    Segmented text:
    {seg}
    """

    classified = _get_openai_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": classification_prompt}],
        temperature=0,
        response_format={
            "type": "json_object"
        },  # <-- ensures valid JSON if supported
    )

    # Safely parse the result
    try:
        # New SDK (with structured output)
        result = classified.choices[0].message.parsed  # type: ignore
    except AttributeError:
        # Fallback for older SDKs
        raw_output = classified.choices[0].message.content
        result = json.loads(raw_output)  # type: ignore

    return result
