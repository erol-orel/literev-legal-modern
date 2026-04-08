# Document Refinement & Table Choice

The refinement module implements an iterative human-in-the-loop workflow where users progressively build their document set by marking documents as relevant (YES), irrelevant (NO), or undecided (MAYBE), then expanding to spatial neighbors of relevant documents.

Source file: [src/literev/libs/table_choice.py](../src/literev/libs/table_choice.py)

---

## Core Concepts

### TableChoice

A `TableChoice` record links a (user, project, document) triple with a display flag and a selection state:

```python
# is_check values:
True    # YES — user confirmed as relevant
False   # NO  — user excluded as irrelevant
None    # MAYBE / not yet decided (default)
```

### ProjectRefinement

An independent refinement workflow on a project. One project can have multiple refinements (e.g. one per research angle). Refinements can branch from each other via `origin` (self-referential FK).

### RefinementIteration

A snapshot within a refinement:

```
Iteration 1
├── checked_documents_ids   = [101, 103, 107]   (YES)
├── excluded_documents_ids  = [102, 104]          (NO)
├── new_neighbors_ids       = [108, 109, 110]     (added via neighbor expansion)
└── result_documents_ids    = [101, 103, 107, 108, 109, 110]

Iteration 2 (child of Iteration 1)
└── user marks 108 as NO, 109 as YES, etc.
```

---

## User Workflow

```
1. Project created + documents clustered
        │
        ▼
2. User sees document table (all documents displayed)
   [render_table_choice()]
        │
        ▼
3. User marks documents:
   - YES (relevant) → is_check = True
   - NO (irrelevant) → is_check = False
   - MAYBE → is_check = None
        │
        ▼
4. User clicks "Iterate"
   [iterate_check_list()]
        │
        ├── Creates new RefinementIteration
        ├── Finds 10 nearest neighbors for each YES document
        │   [neighbour_document()]
        ├── Adds neighbors to display (to_display = True)
        └── User sees expanded document set
        │
        ▼
5. Repeat steps 3–4 until satisfied
        │
        ▼
6. Final document set → use for RAG or export
```

---

## Rendering

### render_table_choice

```python
def render_table_choice(
    project: Project,
    tablechoice: QuerySet[TableChoice],
) -> tuple[list[dict], bool, bool]:
    """
    Prepares document data for template rendering.
    
    Returns:
        rendered_docs: list[dict]  — each dict contains document fields +
                                     display metadata (highlights, scores)
        has_hdbscan_scores: bool   — whether HDBSCAN scores are available
        has_es_scores: bool        — whether ES scores are available
    """
```

Each document dict in `rendered_docs` includes:
- All `Document` model fields
- `is_check`: current selection state
- `to_display`: whether visible in current view
- Highlighted keywords (from query terms)
- Topic and HDBSCAN score from `ClusterElement`
- ES relevance score

### highlight_words

```python
def highlight_words(
    text: str,
    words_to_highlight: list[str],
    style_class: str,
) -> str:
    """Wraps query keywords in <span class="{style_class}"> tags."""

def highlight_words_topic(
    text: str,
    words_to_highlight: list[str],
    color_code: str,
) -> str:
    """Highlights topic words with inline color style."""
```

---

## Sorting

```python
def sort_table_choice(
    project: Project,
    tablechoice: QuerySet[TableChoice],
    order_by: str,
) -> list[TableChoice]:
    """
    Sorts the document table.
    
    order_by values:
        "decision_date"   — ascending date
        "-decision_date"  — descending date
        "es_score"        — Elasticsearch relevance (descending)
    """
```

HDBSCAN-score sorting is handled by:

```python
def sort_by_keyword_score(
    project: Project,
    tablechoice: QuerySet[TableChoice],
    keyword: str,
) -> list[TableChoice]:
    """Sorts by similarity to a keyword using spacy lemmatization."""
```

---

## Neighbor Expansion

The key innovation of the refinement workflow: when you mark a document as relevant, its nearest neighbors in the 2D PaCMAP space are surfaced as candidates.

```python
def neighbour_document(document: Document, project: Project) -> list[Document]:
    """
    Returns the 10 nearest documents to `document` in PaCMAP 2D space.
    
    Algorithm:
        1. Load all ClusterElement positions for this project
        2. Compute Euclidean distance from document to all others
        3. Return 10 closest (excluding the document itself)
    """
```

This works because documents close in PaCMAP space are semantically similar — they share topic-relevant terms in TF-IDF space.

---

## Iteration Management

### Creating an iteration

```python
def create_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    parent_iteration: RefinementIteration | None = None,
) -> None:
    """
    Creates a new RefinementIteration.
    Saves the current TableChoice state as the iteration snapshot.
    """
```

### Getting iteration state

```python
def get_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
) -> None:
    """Restores TableChoice state from a saved iteration."""
```

### Navigating back

```python
def remove_iteration_get_parent(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
) -> int | None:
    """Removes current iteration and returns parent iteration ID."""
```

### Resetting

```python
def reset_table_choice(
    user: User,
    project: Project,
    refinement_id: int,
) -> None:
    """Resets all TableChoice states to unselected (is_check=None)."""
```

### Iteration history for rendering

```python
def get_iterations_render(
    refinement_id: int,
    active_iteration_id: int,
) -> list[dict[str, int | bool | str]]:
    """
    Returns iteration history list for breadcrumb/navigation rendering.
    Each item: {id, number, is_active, label}
    """
```

---

## TableChoice Update Functions

### Bulk mark operations

```python
def check_all2_yes_tablechoice(user: User, project: Project) -> None:
    """Marks all displayed documents as YES."""

def check_all2_maybe_tablechoice(user: User, project: Project) -> None:
    """Marks all displayed documents as MAYBE."""
```

### Per-page update (from API)

```python
def update_checked_document_page(
    user: User,
    project: Project,
    check_list_yes: list[int],     # document IDs → YES
    check_list_no: list[int],      # document IDs → NO
    check_list_maybe: list[int],   # document IDs → MAYBE
) -> None:
    """Updates is_check for the provided document ID lists."""
```

This is called by `UpdateTableChoiceAPIView` on every page save.

### Neighbor display update

```python
def update_neighbour_table_choice(
    user: User,
    project: Project,
    excluded_set: set[int],
) -> None:
    """
    Shows documents in the neighbor set.
    excluded_set: document IDs to keep hidden (already marked NO).
    """

def update_document_to_display_table_choice(
    user: User,
    project: Project,
) -> None:
    """Refreshes to_display for all TableChoice records based on current state."""
```

### Iteration application

```python
def update_check_list_iteration(
    user: User,
    project: Project,
    iteration_id: int,
) -> None:
    """Applies the checked/excluded lists from a RefinementIteration to
    the current TableChoice state."""
```

---

## Background Processing

### Iterating with neighbors

```python
def back_process_iterate(
    user: User,
    project: Project,
    refinement_id: int,
    parent_iteration_id: int,
) -> None:
    """
    Background task:
    1. Collects YES documents from current TableChoice
    2. Expands to their 10 nearest PaCMAP neighbors
    3. Creates new RefinementIteration with expanded set
    4. Updates TableChoice display flags
    """

def iterate_check_list(
    user: User,
    project: Project,
    refinement_id: int,
    active_iteration_id: int,
) -> None:
    """Entry point for the iterate action. Spawns back_process_iterate."""
```

---

## RAG Integration

After refinement, the user's YES documents become the input for RAG:

```python
def create_tablechoice_rag_iteration(user: User, project: Project) -> None:
    """
    Creates a TableChoice iteration snapshot specifically for RAG input.
    Locks the current YES document set as the RAG document subset.
    """
```

The document IDs passed to `POST /api/project/{id}/rag/` come from `RefinementIteration.result_documents_ids`.

---

## Utility Functions

```python
def divide_in_chunks(id_list: list[int], batch_size: int) -> Iterator[list[int]]:
    """Splits a list into batches. Used for bulk DB updates."""

def all_display_table_choice(project: Project) -> None:
    """Sets to_display=True for all documents in a project."""

def update_new_table_choice(
    user: User,
    project: Project,
    document_ids_list: list[int],
) -> None:
    """Creates TableChoice records for a new set of document IDs."""
```

---

## Data Flow Summary

```
Initial state:
  All documents: to_display=True, is_initial=True, is_check=None

After user marks selections:
  YES docs: is_check=True
  NO docs:  is_check=False

After iterate:
  New RefinementIteration created (snapshot of current state)
  Neighbors of YES docs: to_display=True, is_initial=False
  NO docs: to_display=False (hidden from view)

After subsequent iteration:
  Next RefinementIteration created (parent = previous)
  User can navigate back via remove_iteration_get_parent()
```
