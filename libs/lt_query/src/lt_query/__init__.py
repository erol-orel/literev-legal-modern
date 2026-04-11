from .parsing import (
    ElasticSearchQueryBuilder,
    Parser,
    extract_after_endroit,
    parse_expression,
    process_search_query,
    process_search_query_elasticsearch,
    tokenize_expression,
    validate_expression,
)

PROMPT_TEMPLATE = ""


def convert_nl_to_boolean(*args, **kwargs):
    raise ModuleNotFoundError(
        "lt_query.convert_nl_to_boolean requires the optional 'litellm' dependency"
    )


try:
    from .boolean_query import (
        PROMPT_TEMPLATE as _PROMPT_TEMPLATE,
    )
    from .boolean_query import (
        convert_nl_to_boolean as _convert_nl_to_boolean,
    )
except ModuleNotFoundError as exc:
    if exc.name != "litellm":
        raise
else:
    PROMPT_TEMPLATE = _PROMPT_TEMPLATE
    convert_nl_to_boolean = _convert_nl_to_boolean

__all__ = [
    "PROMPT_TEMPLATE",
    "ElasticSearchQueryBuilder",
    "Parser",
    "convert_nl_to_boolean",
    "extract_after_endroit",
    "parse_expression",
    "process_search_query",
    "process_search_query_elasticsearch",
    "tokenize_expression",
    "validate_expression",
]
