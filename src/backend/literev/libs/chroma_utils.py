from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

from chromadb import PersistentClient
from django.conf import settings
from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-4.1-mini"
OPENAI_API_KEY = settings.OPENAI_API_KEY

N_TOP_CHUNKS = 8
CACHE_DIR = settings.LITEREV_CACHE_DIR
CHROMA_DIR = CACHE_DIR / "chroma_db"
CHROMA_DIR_PENAL = CACHE_DIR / "chroma_db_penal"
CHROMA_DIR_ADM = CACHE_DIR / "chroma_db_adm"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
chroma_client = PersistentClient(CHROMA_DIR)
chroma_client_penal = PersistentClient(CHROMA_DIR_PENAL)
# chroma_client_adm = PersistentClient(CHROMA_DIR_ADM)

DOCUMENT_SECTIONS = [
    "Majeure",
    "Mineure-Faits",
    "Mineure-Subsommation",
    "Conclusion",
]
# Get Geneva local date and time
geneva_dt = datetime.now(ZoneInfo("Europe/Zurich"))

# Date string, e.g.: "7 juin 2024, 11:34 (heure locale de Genève)"
date_str = geneva_dt.strftime("%-d %B %Y, %H:%M (heure locale de Genève)")

STRICT_GUARD = """
Date de la réponse : {date}
Vous etes un expert du droit suisse specialise dans la jurisprudence.
Vous devez fonder votre raisonnement uniquement sur le contexte fourni.
Si quelque chose ne peut pas etre deduit strictement de celui-ci, repondez: "L'information requise n'est pas indiquee dans le contexte".
N'ajoutez jamais de connaissances generales ni d'hypotheses.
Veuillez répondre strictement en français.
""".format(date=date_str)

PROMPTS = [
    {
        "name": "A_strict_context",
        "system": STRICT_GUARD,
        "user_template": """
        Question: {question}

        Contexte: {context}

        **Instruction** : Réponds à la question ci-dessus en te basant uniquement sur le contexte fourni.

        Structure ta réponse **strictement** en un objet JSON où chaque clé ("Examen des faits", "Analyse juridique (subsomption)", "Décision finale") a pour valeur une unique chaîne de caractères résumant la section concernée. N'utilise ni listes, ni dictionnaires imbriqués. Si tu veux séparer des éléments, utilise des points, des puces, ou des retours à la ligne dans la chaîne, mais jamais d'autres structures.

        Exemple attendu :
        {{
            "Examen des faits": "Résumé des faits ici, sous forme de texte.",
            "Analyse juridique (subsomption)": "Résumé de l'analyse ici, sous forme de texte.",
            "Décision finale": "Résumé de la décision finale ici, sous forme de texte."
        }}

        Retourne uniquement ce JSON, sans ajout d'explications ni de texte supplémentaire.
        """,
        "max_tokens": 2400,
        "temperature": 0.1,
    },
]


# Keeping ROUTING_HINTS to future implementation

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
        if (
            sec == "Majeure"
        ):  # Adding this to avoid retrieving answers from majeure section
            continue
        if items:
            parts.append(f"## {sec}\n" + "\n".join(f"{i}" for i in items))
    ctx = "\n\n".join(parts)

    if not ctx.strip():
        return "No relevant context was found for this document."

    # getting the ans
    prompt = PROMPTS[0]
    # max_tokens = cast(int, prompt["max_tokens"]) # Commenting this line to avoid having trunkated answers
    temperature = cast(float, prompt["temperature"])

    # Prepare messages for the API
    system_message = cast(
        dict[str, str], {"role": "system", "content": prompt["system"]}
    )
    user_template = cast(str, prompt["user_template"])
    user_message = {
        "role": "user",
        "content": user_template.format(question=question, context=ctx),
    }

    # Call the OpenAI ChatCompletion endpoint
    response = openai_client.chat.completions.create(  # type: ignore
        model=CHAT_MODEL,
        messages=[system_message, user_message],
        response_format={"type": "json_object"},
        # max_completion_tokens=max_tokens, # Commenting this line to avoid having trunkated answers
        temperature=temperature,
    )

    answer = response.choices[0].message.content

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


def get_best_section_chunks_new(
    record_key, question, embedded_question, collection
):
    # Perform one query for all sections for this record_key
    results = collection.query(
        query_embeddings=embedded_question,
        where={
            "record_key": record_key,
        },
        include=["documents", "metadatas"],
    )

    # Initialize a dict for chunks per section
    blocks: dict[str, list[str]] = {
        section: [] for section in DOCUMENT_SECTIONS
    }

    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    # Group documents by section (using metadata["section"])
    for doc, meta in zip(documents[0], metadatas[0]):
        section = meta.get("section")

        if section in blocks:
            blocks[section].append(doc)

    # Trim each section to N_TOP_CHUNKS
    for section in blocks:
        blocks[section] = blocks[section][:N_TOP_CHUNKS]

    return blocks


def get_majeures_summary(query, majeures):
    context = "\n\n".join(majeures)

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
