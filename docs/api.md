# REST API

The API is built with Django REST Framework. All endpoints require authentication unless noted. Source files:

- Views: [src/literev/api/views.py](../src/literev/api/views.py)
- Serializers: [src/literev/api/serializers.py](../src/literev/api/serializers.py)
- Permissions: [src/literev/api/permissions.py](../src/literev/api/permissions.py)

---

## Authentication

All API endpoints require `IsAuthenticated` (session auth + CSRF). The API is consumed by the Django-rendered frontend — it is not a public API.

Include CSRF token in state-changing requests:
```
X-CSRFToken: <token from cookie>
```

---

## Endpoints

### Boolean Query Conversion

```
GET /api/project/convert-to-boolean-query/<natural_language>/<api_key>/
```

Converts a natural language French query into an Elasticsearch Boolean query using GPT-4.1-mini.

**Parameters:**

| Name | Location | Type | Description |
|---|---|---|---|
| `natural_language` | path | string | French natural language query |
| `api_key` | path | string | OpenAI API key |

**Response 200:**
```json
{
  "boolean_query": "tribunal AND (administratif OR civil) NOT penal"
}
```

**Response 400:**
```json
{
  "error": "conversion failed: ..."
}
```

**Notes:**
- The query string is normalized (lowercase, trimmed) before sending to OpenAI
- The LLM is prompted to produce valid Boolean syntax for the project's ES schema
- This endpoint is used in the project creation wizard

---

### Project RAG — Get

```
GET /api/project/<project_id>/rag/
GET /api/project/<project_id>/rag/<rag_id>/
```

Fetches RAG results for a project.

- With `rag_id=0` (or omitted): returns the most recent `ProjectRAG` for this project
- With `rag_id>0`: returns that specific `ProjectRAG`

**Permission check:** user must be the project owner OR the project must appear in their shared projects list.

**Response 200:**
```json
{
  "id": 42,
  "project": 7,
  "query": "Quels sont les critères retenus pour la faute grave ?",
  "created_at": "2024-03-15T14:22:00Z",
  "status": "completed",
  "status_display": "Completed",
  "valid_answer_count": 18,
  "num_documents": 20
}
```

**Response 404:** project or RAG record not found, or access denied.

---

### Project RAG — Create

```
POST /api/project/<project_id>/rag/
```

Creates a new `ProjectRAG` and triggers the async RAG pipeline.

**Request body:**
```json
{
  "query": "Quels sont les critères retenus pour la faute grave ?",
  "documents_ids": [101, 102, 103, 104]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Question to answer (max 500 chars) |
| `documents_ids` | list[int] | yes | Document PKs to run RAG against |

**Response 201:**
```json
{
  "id": 43,
  "project": 7,
  "query": "Quels sont les critères retenus pour la faute grave ?",
  "created_at": "2024-03-15T14:23:00Z",
  "status": "in_progress",
  "status_display": "In Progress",
  "valid_answer_count": 0,
  "num_documents": 4
}
```

**Response 400:**
```json
{
  "error": "query is required"
}
```

**Notes:**
- The async Celery task updates `ProjectRAG.status` as it progresses through stages
- Poll `GET /api/project/<id>/rag/<rag_id>/` to track status
- `valid_answer_count` increments as documents are processed

---

### ProjectRAG ViewSet

```
GET    /api/rag/
GET    /api/rag/<id>/
POST   /api/rag/
PUT    /api/rag/<id>/
PATCH  /api/rag/<id>/
DELETE /api/rag/<id>/
```

Standard DRF `ModelViewSet` for `ProjectRAG`. Requires `IsAuthenticated`.

---

### ProjectDocumentRAG ViewSet

```
GET /api/rag-document/
GET /api/rag-document/<id>/
```

Standard DRF `ModelViewSet` for `ProjectDocumentRAG`.

**Filtering:** supports `?project_rag=<id>` to retrieve all answers for a specific RAG run.

**Response 200 (list item):**
```json
{
  "id": 201,
  "project_rag": 43,
  "document": {
    "id": 101,
    "procedure_type": "Recours de droit public",
    "decision_type": "Arrêt",
    "decision_date": "2023-11-14",
    "result": "Rejet",
    "standards": "CO 337",
    "procedure_year": "2023",
    "url_document": "https://..."
  },
  "citation": "La faute grave suppose un manquement particulièrement sérieux...",
  "answer": "Le tribunal a retenu trois critères: ...",
  "confidence_score": 0.87
}
```

**Notes:**
- `document` is expanded by `ProjectDocumentRAGSerializer.to_representation()` — it is not just the FK integer
- `confidence_score=0.0` means the LLM returned an empty/invalid answer

---

### Update Table Choice

```
PUT /api/project/<project_id>/table-choice/
PUT /api/project/<project_id>/table-choice/<iteration_id>/
PUT /api/project/<project_id>/table-choice/<iteration_id>/<page>/
```

Updates document selection states (YES/NO/MAYBE) for an ongoing refinement.

**Request body:**
```json
{
  "selected_documents": [101, 103],
  "deselected_documents": [102],
  "maybe_documents": [104]
}
```

| Field | Type | Description |
|---|---|---|
| `selected_documents` | list[int] | document IDs to mark as YES (`is_check=True`) |
| `deselected_documents` | list[int] | document IDs to mark as NO (`is_check=False`) |
| `maybe_documents` | list[int] | document IDs to mark as MAYBE (`is_check=None`) |

**Parameters:**

| Name | Default | Description |
|---|---|---|
| `iteration_id` | `-1` | `-1` = current iteration; positive int = specific iteration |
| `page` | `1` | current document page (for multi-page views) |

**Response 200:** `{"status": "ok"}`

**Response 403:** user does not own the project

**Response 400:** invalid request body

---

## Serializers

### ProjectRAGSerializer

```python
class ProjectRAGSerializer(serializers.ModelSerializer):
    fields = ['id', 'project', 'query', 'created_at', 'status',
              'status_display', 'valid_answer_count', 'num_documents']
    read_only = ['id', 'project', 'created_at']
```

`status_display` is a computed field returning the human-readable label of the `status` choice field.

### ProjectDocumentRAGSerializer

```python
class ProjectDocumentRAGSerializer(serializers.ModelSerializer):
    fields = ['id', 'project_rag', 'document', 'citation',
              'answer', 'confidence_score']
    read_only = ['id', 'project_rag', 'document']
```

`to_representation()` replaces the `document` FK integer with an expanded dict:
```python
{
    'id': document.id,
    'procedure_type': document.procedure_type,
    'decision_type': document.decision_type,
    'decision_date': document.decision_date,
    'result': document.result,
    'standards': document.standards,
    'procedure_year': document.procedure_year,
    'url_document': document.url_document,  # constructed URL
}
```

---

## Permissions

### IsProjectRAGOwner

Used on `ProjectRAG` objects. Returns `True` if:
- `request.user == obj.project.user`, OR
- `obj.project` appears in the user's shared projects list

### IsProjectRAGDocumentOwner

Used on `ProjectDocumentRAG` objects. Returns `True` if:
- `request.user == obj.project_rag.project.user`

---

## Error Handling Conventions

| HTTP Status | When |
|---|---|
| 200 | Successful read or update |
| 201 | Resource created |
| 400 | Validation error — body contains `{"error": "..."}` |
| 403 | Authenticated but not authorized for this resource |
| 404 | Resource not found or access denied (access denial uses 404 to avoid information leakage) |

---

## Adding a New Endpoint

1. Add the view class to `src/literev/api/views.py`
2. Add the URL pattern to `src/config/urls.py` (or the app-level `urls.py` if it exists)
3. Add a serializer in `src/literev/api/serializers.py` if the endpoint returns model data
4. Add a permission class to `src/literev/api/permissions.py` if ownership checks are needed
5. Write tests in `src/literev/tests/api/`

Always use class-based views (`APIView` or `ModelViewSet`) — never function-based API views.
