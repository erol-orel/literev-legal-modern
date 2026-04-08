# French Legal Text Classification

The legal module classifies French judicial decisions into their structural sections: **Majeure** (legal rule), **Mineure-Faits** (facts), **Mineure-Subsommation** (subsumption), and **Conclusion**.

Source file: [src/literev/legal/extract_minor_major.py](../src/literev/legal/extract_minor_major.py)

---

## Legal Reasoning Structure

French legal decisions follow a syllogistic structure derived from French legal tradition (méthode du syllogisme judiciaire):

```
Majeure        — the legal rule or norm
                 "La faute grave est définie comme..."
                 
Mineure-Faits  — the established facts of the case
                 "En l'espèce, le salarié a..."
                 
Mineure-Subsommation — application of the rule to the facts
                 "Ces éléments constituent bien..."
                 
Conclusion     — the decision outcome
                 "Par conséquent, le licenciement est..."
```

Identifying these sections enables:
- Targeted retrieval (search only in legal rules, or only in facts)
- Structured RAG with section-aware context
- Legal analysis and comparison across decisions

---

## Text Processing Pipeline

### 1. Mojibake Repair

```python
def _fix_mojibake(s: str) -> str:
    """Repairs encoding corruption using ftfy library.
    Handles common French legal text encoding issues:
    - Latin-1 characters decoded as UTF-8 (e.g. 'Ã©' → 'é')
    - Windows-1252 artifacts
    """
```

French legal texts are sometimes served with mixed encodings. `ftfy` heuristically repairs these.

### 2. Text Normalization

```python
def normalize_text(raw: str) -> str:
    """
    Full normalization pipeline:
    1. Fix mojibake (ftfy)
    2. Escape problematic characters
    3. Merge fragmented lines (OCR artifacts, PDF extraction)
    4. Normalize whitespace
    5. Strip leading/trailing whitespace
    
    Returns: Clean normalized text suitable for sentence splitting.
    """
```

### 3. Sentence Splitting

```python
def split_sentences_fr_legal(text: str) -> list[str]:
    """
    French legal-aware sentence tokenizer.
    
    Handles:
    - Legal abbreviations (art., al., ch., para., etc.)
    - Numbered items (1., 2., etc.) — not treated as sentence endings
    - Parenthetical references — (ATF 120 II 150)
    - Decimal numbers — 3.5% not split
    
    Returns: List of sentence strings.
    """
```

Standard sentence splitters fail on legal texts because of:
- Abbreviations like `al.`, `art.`, `ch.` being mistaken for sentence boundaries
- Numbered legal paragraphs (1. ... 2. ...)
- Citation patterns like `ATF 120 II 150, consid. 3b`

The module protects these patterns before splitting, then restores them:

```python
# Protect patterns from being split
DOT = "⟂"  # placeholder character

def _shield(t: str) -> str:
    """Replaces dots in abbreviations/numbers/parentheses with DOT placeholder."""

def _unshield(t: str) -> str:
    """Restores DOT placeholder back to '.'."""
```

**`ABBR` pattern** covers the most common French legal abbreviations:
`art.`, `al.`, `ch.`, `par.`, `para.`, `cf.`, `v.`, `ibid.`, `op. cit.`, `ATF`, `ATF`, etc.

---

## Chunking

```python
def pack_chunks(
    text_chunks: list[str],
    max_lines: int = 8,
    preserve_chunks: bool = False,
    max_tokens: int = 300,
) -> tuple[list[str], list[tuple[int, int]]]:
    """
    Packs individual sentences into larger chunks for LLM classification.
    
    Parameters
    ----------
    text_chunks : list[str]
        Individual sentences from split_sentences_fr_legal()
    max_lines : int
        Maximum sentences per chunk
    preserve_chunks : bool
        If True, don't merge across sentences
    max_tokens : int
        Maximum tokens per chunk (counted with tiktoken)
    
    Returns
    -------
    packed_chunks : list[str]
        Merged text chunks
    original_indices : list[tuple[int, int]]
        (start_idx, end_idx) of original sentences for each chunk
    """
```

Chunks are sized to fit within LLM context while containing enough text for classification context.

---

## LLM Classification

### Pydantic output model

```python
class Classification(BaseModel):
    """Structured classification output from the LLM."""
    # Dynamic fields: chunk_0, chunk_1, ..., chunk_n
    # Each field value: "majeure" | "mineure_faits" | "mineure_subsommation" | "conclusion"
```

The model is built dynamically based on the number of chunks:

```python
def build_consideration_model(count: int):
    """Returns a Pydantic model class with 'chunk_0' ... 'chunk_n' fields."""
```

### Prompt construction

```python
def build_user_prompt(chunks: list[str]) -> str:
    """
    Builds a classification prompt for the LLM.
    
    Format:
        [0] sentence text
        [1] sentence text
        ...
        
    Classify each numbered item as: majeure / mineure_faits /
    mineure_subsommation / conclusion
    """
```

### OpenAI API call

```python
def openai_llm_call(
    prompt: str,
    structured_output: BaseModel,
    api_key: str,
) -> dict | BaseModel:
    """
    Calls OpenAI API with structured output (JSON schema enforcement).
    
    Uses: gpt-4.1-mini with response_format=structured_output
    Handles: retries on API errors, validation failures
    Returns: Classification object or error dict
    """
```

### Validation

```python
def expected_ids(n: int) -> list[str]:
    """Returns ['chunk_0', 'chunk_1', ..., 'chunk_n-1']."""

def validate_classification(n: int, c: Classification) -> Tuple[bool, str]:
    """
    Validates that the LLM classified exactly n chunks
    and all values are valid category names.
    Returns: (is_valid, error_message)
    """
```

---

## Main Classification Workflow

```python
def classify_chunks_llm(
    chunks: list[str],
    n_labels: int,
    llm_fn: Callable,
) -> Classification:
    """
    Main classification pipeline.
    
    1. Build prompt from chunks
    2. Call LLM with structured output
    3. Validate response
    4. Retry up to 3 times on invalid response
    5. Return Classification object
    """
```

### Entry point for full documents

```python
def get_sentences(text: str) -> list[str]:
    """
    Full pipeline for a raw document:
    normalize → split sentences → return list
    """
```

---

## Integration with Django Models and Commands

### Management commands using this module

| Command | What it does |
|---|---|
| `classify_document_sentences` | Classify all project documents into sections |
| `extract_mineur_majeur` | Extract mineure/majeure and save to JSON file |
| `get_record_keys` | Extract section labels and store by record_key |
| `prepare_input` | Prepare classified documents for embedding |
| `prepare_classified_documents` | Prepare documents for embedding by chamber |

### Example usage

```bash
# Classify all documents in a project
python manage.py classify_document_sentences --project-id 42

# Extract and save to JSON
python manage.py extract_mineur_majeur \
    --project-id 42 \
    --output /opt/data/literev/classifications/project_42.json
```

### Output format

```json
{
  "record_key_abc123": {
    "majeure": "La faute grave suppose un manquement...",
    "mineure_faits": "En l'espèce, le salarié a refusé...",
    "mineure_subsommation": "Ces éléments caractérisent...",
    "conclusion": "Par conséquent, le licenciement..."
  }
}
```

---

## MinorMajorPair Model

Used in the RAG pipeline for structured section extraction:

```python
class MinorMajorPair(BaseModel):
    mineure: str    # minor premise (facts + subsomption)
    majeure: str    # major premise (legal rule)
```

When a RAG query targets the legal rule specifically, only the `majeure` section is sent to the LLM as context, improving answer quality.

---

## Design Considerations

**Why sentence-level classification?**
Paragraph-level classification is unreliable in French legal texts because multiple sections often appear within a single paragraph. Sentence-level gives finer granularity.

**Why not use a fine-tuned classifier?**
The variety of writing styles across chambers and decades makes rule-based and fine-tuned classifiers brittle. GPT-4.1-mini with structured output provides robust zero-shot classification.

**Token budget management**
`pack_chunks()` respects `max_tokens=300` per chunk using `tiktoken`. This ensures the full document (potentially hundreds of sentences) fits within the LLM context window across multiple API calls.

**Retry logic**
`classify_chunks_llm()` retries up to 3 times if the LLM returns an invalid classification (wrong number of items, invalid category names). On persistent failure, it falls back to labeling all chunks as `"majeure"`.
