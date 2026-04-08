# Query Parsing

The parsing module translates user-submitted Boolean search expressions into Elasticsearch query DSL. It implements a full lexer → parser → AST → code-generator pipeline.

Source file: [src/literev/libs/parsing.py](../src/literev/libs/parsing.py)

---

## Supported Query Syntax

Users write queries in a subset of Boolean logic:

```
# Simple keyword
tribunal administratif

# Boolean operators (case-insensitive)
emploi AND licenciement
dommage OR préjudice
responsabilité NOT pénale

# Grouping with parentheses
(emploi OR travail) AND (licenciement OR congédiement)

# Quoted phrases (exact match)
"faute grave" AND licenciement

# Negation at phrase level
NOT "faute lourde"

# Nested expressions
((A OR B) AND C) NOT (D AND E)
```

Operators: `AND`, `OR`, `NOT` (all uppercase or lowercase)

---

## Architecture: Lexer → AST → ES Query

```
User input string
        │
        ▼
tokenize_expression()   ← splits into Token objects
        │
        ▼
validate_expression()   ← checks syntax rules
        │
        ▼
Parser.parse()          ← builds Abstract Syntax Tree (AST)
        │
        ▼
ElasticSearchQueryBuilder.build()   ← AST → ES query dict
        │
        ▼
process_search_query_elasticsearch()  ← adds date filters
```

---

## Stage 1: Tokenization

```python
def tokenize_expression(query: str) -> list[Token]:
    """Parses a search query string into a list of Token objects.
    
    Normalizes consecutive quotes, handles quoted phrases as single tokens.
    """
```

### Token types (TokenKind enum)

| Kind | Examples | Notes |
|---|---|---|
| `SUBJECT` | `tribunal`, `"faute grave"` | keywords and quoted phrases |
| `CONNECTOR_AND` | `AND`, `and` | logical AND |
| `CONNECTOR_OR` | `OR`, `or` | logical OR |
| `NEGATION_NOT` | `NOT`, `not` | logical NOT |
| `OPEN_PARENTHESIS` | `(` | |
| `CLOSE_PARENTHESIS` | `)` | |

### Token dataclass

```python
@dataclass
class Token:
    _value: str
    kind: TokenKind

    @property
    def value(self) -> str:
        """Returns uppercase for keywords (AND/OR/NOT), original for subjects."""

    def is_keyword(self) -> bool
    def is_connector(self) -> bool        # AND or OR
    def is_connector_and(self) -> bool
    def is_connector_or(self) -> bool
    def is_negation(self) -> bool
    def is_paren(self) -> bool            # ( or )
    def is_open_paren(self) -> bool
    def is_close_paren(self) -> bool
    def is_subject(self) -> bool
```

---

## Stage 2: Validation

```python
def validate_expression(tokens: list[Token]) -> bool:
    """Validates syntactic correctness of a token sequence.
    
    Checks:
    - No empty expression
    - No empty parentheses ()
    - All quotes are matched (even number)
    - All parentheses are balanced
    - Logical operators have operands on both sides
    - No consecutive subjects without operator
    
    Raises: ExpressionValidationError subclass on failure
    """
```

### Exception hierarchy

```
ExpressionValidationError (base)
├── EmptyQueryError             — empty input or only whitespace
├── EmptyParenthesisError       — () with nothing inside
├── UnmatchedQuotesError        — odd number of quote characters
├── UnmatchedParenthesesError   — mismatched ( and )
└── LogicalOperatorError        — operator without operands
```

---

## Stage 3: Parsing (AST Construction)

```python
class Parser:
    """Recursive descent parser. Implements operator precedence:
    NOT > AND > OR (standard Boolean logic order)."""
    
    def parse(self) -> Node:
        """Entry point. Returns root AST node."""
```

### AST Node types

```python
class Node:           # abstract base
class SubjectNode(Node):      # leaf — holds a search term
    value: str
class AndNode(Node):          # binary — left AND right
    left: Node
    right: Node
class OrNode(Node):           # binary — left OR right
    left: Node
    right: Node
class NotNode(Node):          # unary — NOT operand
    operand: Node
```

**Example:**

Input: `"faute grave" AND (emploi OR travail)`

AST:
```
AndNode
├── SubjectNode("faute grave")
└── OrNode
    ├── SubjectNode("emploi")
    └── SubjectNode("travail")
```

---

## Stage 4: Elasticsearch Query Generation

```python
class ElasticSearchQueryBuilder:
    """Converts an AST into an Elasticsearch boolean query dict."""
    
    def build(self, node: Node) -> dict:
        """Recursively builds ES query from AST."""
```

### Mapping from AST to ES query DSL

| AST Node | ES query |
|---|---|
| `SubjectNode("term")` | `{"match": {"document_text": "term"}}` |
| `SubjectNode('"phrase"')` | `{"match_phrase": {"document_text": "phrase"}}` |
| `AndNode(left, right)` | `{"bool": {"must": [left_query, right_query]}}` |
| `OrNode(left, right)` | `{"bool": {"should": [left_query, right_query]}}` |
| `NotNode(operand)` | `{"bool": {"must_not": [operand_query]}}` |

**Example output:**

Input: `"faute grave" AND (emploi OR travail)`

```json
{
  "bool": {
    "must": [
      {"match_phrase": {"document_text": "faute grave"}},
      {"bool": {
        "should": [
          {"match": {"document_text": "emploi"}},
          {"match": {"document_text": "travail"}}
        ]
      }}
    ]
  }
}
```

---

## Full Pipeline Entry Points

### For internal use (returns dict)

```python
def process_search_query_elasticsearch(
    search_query: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> dict:
    """
    Full pipeline: tokenize → validate → parse → ES query dict.
    Adds date range filter to the ES query.
    
    Returns: Elasticsearch query dict ready to pass to the client.
    Raises: ExpressionValidationError if query is invalid.
    """
```

### For intermediate use

```python
def process_search_query(search_expr: str, ...) -> ...:
    """Main query processing pipeline. Can return partial results."""
```

### Text extraction helper

```python
def extract_after_endroit(text: str) -> str:
    """Extracts text appearing after the keyword 'endroit' in a document.
    Used for extracting location-specific legal text."""
```

---

## Natural Language → Boolean Query Conversion

The API endpoint `GET /api/project/convert-to-boolean-query/<nl_query>/<api_key>/` wraps an LLM call to translate natural French text into Boolean syntax:

```
User: "les cas de licenciement abusif dans le secteur privé"
LLM:  "licenciement AND (abusif OR injustifié) AND (salarié OR employé)"
```

This uses `ConvertToBooleanQueryAPIView` in [src/literev/api/views.py](../src/literev/api/views.py). The output is then fed into `process_search_query_elasticsearch()`.

---

## Error Handling

All validation errors inherit from `ExpressionValidationError`. The view layer catches these and returns HTTP 400 with the error message.

```python
try:
    es_query = process_search_query_elasticsearch(query, start, end)
except EmptyQueryError:
    return Response({"error": "Query cannot be empty"}, status=400)
except UnmatchedParenthesesError as e:
    return Response({"error": str(e)}, status=400)
except ExpressionValidationError as e:
    return Response({"error": str(e)}, status=400)
```

---

## Testing Query Parsing

```python
# Example from tests/etl/
def test_boolean_query_and():
    tokens = tokenize_expression("emploi AND licenciement")
    assert validate_expression(tokens)
    query = process_search_query_elasticsearch("emploi AND licenciement", start, end)
    assert query["bool"]["must"][0]["match"]["document_text"] == "emploi"

def test_empty_query_raises():
    with pytest.raises(EmptyQueryError):
        tokenize_expression("")

def test_unmatched_parentheses():
    with pytest.raises(UnmatchedParenthesesError):
        validate_expression(tokenize_expression("(emploi AND travail"))
```

Key edge cases to test:
- Nested parentheses
- Quoted phrases with spaces
- Mixed case operators (`and`, `AND`, `And`)
- NOT at the start of expression
- Empty parentheses `()`
- Odd number of quotes
