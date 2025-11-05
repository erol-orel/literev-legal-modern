from chromadb import PersistentClient
from django.conf import settings
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-4.1-mini"
OPENAI_API_KEY = settings.OPENAI_API_KEY

N_TOP_CHUNKS = 5
CACHE_DIR = settings.LITEREV_CACHE_DIR
CHROMA_DIR = CACHE_DIR / "chroma_db"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
chroma_client = PersistentClient(CHROMA_DIR)

DOCUMENT_SECTIONS = [
    "Metadata",
    "Majeure",
    "Mineure-Faits",
    "Mineure-Subsommation",
    "Conclusion",
]


SYLLOGISM_QA_TEMPLATE = """
You are a Swiss legal reasoning assistant. Use the syllogistic structure of Swiss judgments to answer.

When answering:
- Always reply ONLY as a valid JSON object.
- Answer the following query strictly as a JSON object matching the Python type dict[str, list[str]]. The keys should be strings, and their values lists of strings.
- Use these JSON keys as applicable: "Majeure", "Faits", "Subsommation", "Conclusion", "Metadata".
- If about legal rules → use Majeure.
- If about facts → use Mineure-Faits.
- If about application → use Mineure-Subsommation.
- If about decision → use Conclusion.
- If about procedural/context → use Metadata.
- Explain reasoning explicitly and cite the sections you used.
- Do NOT invent facts or legal rules not present.

Question: {question}

Context:
{context}

Answer (respond ONLY as valid JSON with the above keys):
"""
ROUTING_HINTS = {
    "majeure": [
        "règle",
        "base légale",
        "article",
        "jurisprudence",
        "quelle règle",
        "fondement",
    ],
    "faits": [
        "faits",
        "que s'est-il passé",
        "chronologie",
        "où",
        "quand",
        "qui",
    ],
    "subsommation": [
        "application",
        "pourquoi",
        "comment",
        "motivation",
        "raison",
        "analyse",
    ],
    "conclusion": [
        "décision",
        "dispositif",
        "issue",
        "remède",
        "recours",
        "résultat",
        "a-t-il gagné",
    ],
    "metadata": ["tribunal", "date", "référence", "numéro", "section"],
}

SECTION_MAP = {
    "majeure": ["Majeure"],
    "faits": ["Mineure-Faits"],
    "subsommation": ["Mineure-Subsommation"],
    "conclusion": ["Conclusion"],
    "metadata": ["Metadata"],
}


def route_question(question: str) -> list[str]:
    q = question.lower()
    scores = {k: 0 for k in ROUTING_HINTS}
    for k, hints in ROUTING_HINTS.items():
        for h in hints:
            if h in q:
                scores[k] += 1
    # pick top scoring; if tie or none, return all
    top = [k for k, v in scores.items() if v == max(scores.values()) and v > 0]
    if not top:
        return [
            "Majeure",
            "Mineure-Faits",
            "Mineure-Subsommation",
            "Conclusion",
            "Metadata",
        ]
    # Map to sections
    sections = []
    for k in top:
        sections.extend(SECTION_MAP[k])
    return sections or [
        "Majeure",
        "Mineure-Faits",
        "Mineure-Subsommation",
        "Conclusion",
        "Metadata",
    ]


def ask_to_openai(question: str, context: str) -> str:
    if not context.strip():
        return "No relevant context was found for this document."
    system = "You are a helpful assistant. Answer using only the provided context. If the context is insufficient, say you don't know. Cite snippets like [1], [2] when relevant."
    user = f"Question: {question}\n\nContext:\n{context}"
    chat = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    answer = chat.choices[0].message.content
    return answer if answer else ""


def llm_answer(question: str, blocks: dict[str, list[str]]) -> str:
    # building structured context
    parts = []
    for sec, items in blocks.items():
        if items:
            parts.append(f"## {sec}\n" + "\n".join(f"- {i}" for i in items))
    ctx = "\n\n".join(parts)

    # getting the ans
    prompt = SYLLOGISM_QA_TEMPLATE.format(question=question, context=ctx)
    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a careful Swiss legal assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    answer = resp.choices[0].message.content
    return answer if answer else ""


def get_best_section_chunks(
    record_key, question, embedded_question, collection
):
    blocks = {}
    # sections = route_question(question)
    for section in DOCUMENT_SECTIONS:
        results = collection.query(
            query_embeddings=embedded_question,
            where={
                "$and": [
                    {"record_key": record_key},
                    {"section": section},
                ]
            },
            n_results=N_TOP_CHUNKS,
            include=["documents"],
        )

        sentences = results.get("documents", [])

        blocks[section] = sentences[0] if sentences else []

    return blocks


def get_majeures_summary(query, answers):
    context = "\n\n".join(answers)

    prompt = (
        "Based on ALL of the given answers extracted from the documents, "
        "write a concise and coherent summary as a single sentence, in French. "
        "Summarize only the legal perspectives that are directly mentioned or clearly supported by the answers. "
        "Do not invent or infer arguments that are not explicitly stated. "
        "Avoid vague or emotional expressions. Focus on legal arguments and facts. "
        "If there is absolutely no relevant information, return exactly: `Résumé non disponible`. "
        "\n\n"
        "**Instructions:**\n"
        "1. Do NOT mention specific names or individual cases.\n"
        "2. If all answers agree on one idea, return a single-sentence summary.\n"
        "3. If there are multiple legal arguments or points of view:\n"
        "   - Provide a short summary sentence.\n"
        "The original question is: `{query}`\n\n"
        "Given Answers:\n"
        "{context}"
    ).format(query=query, context=context)

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a careful Swiss legal assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    answer = resp.choices[0].message.content

    return answer if answer else ""
