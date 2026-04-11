"""
This module handles parsing boolean search queries. It includes functions for
tokenizing, validating, and parsing search expressions.

Workflow:
1. Tokenization: Converts queries into tokens (subjects, connectors, etc.).
2. Validation: Ensures syntactical correctness of tokenized queries, checking
   operators, parentheses balance, and quote matching.
3. Parsing: Translates validated tokens into structured query strings, usable
   in search systems or databases.
"""

from __future__ import annotations

import datetime
import re

from dataclasses import dataclass
from enum import Enum
from pprint import pformat
from typing import Any, Optional


class ExpressionValidationError(Exception):
    """Exception raised for errors in the boolean query validation."""


class EmptyQueryError(ExpressionValidationError):
    """Exception raised for empty queries in the boolean query validation."""


class EmptyParenthesisError(ExpressionValidationError):
    """Exception raised for empty parentheses in the boolean query validation."""


class UnmatchedQuotesError(ExpressionValidationError):
    """Exception raised for unclosed quotes in the boolean query validation."""


class UnmatchedParenthesesError(ExpressionValidationError):
    """Exception raised for unmatched parentheses in the boolean query validation."""


class LogicalOperatorError(ExpressionValidationError):
    """Exception raised for logical operators in the boolean query validation."""


class TokenKind(Enum):
    """TokenKind enumeration for known token types."""

    SUBJECT = 1
    CONNECTOR_AND = 2
    CONNECTOR_OR = 3
    NEGATION_NOT = 4
    OPEN_PARENTHESIS = 5
    CLOSE_PARENTHESIS = 6


TOKEN_MAP = {
    "AND": TokenKind.CONNECTOR_AND,
    "OR": TokenKind.CONNECTOR_OR,
    "NOT": TokenKind.NEGATION_NOT,
    "(": TokenKind.OPEN_PARENTHESIS,
    ")": TokenKind.CLOSE_PARENTHESIS,
}


@dataclass
class Token:
    """Dataclass for tokens."""

    _value: str
    kind: TokenKind

    @property
    def value(self) -> str:
        return self._value.upper() if self.is_keyword() else self._value

    def is_keyword(self) -> bool:
        """Determines if token is (AND, OR or NOT)"""
        return self.is_connector() or self.is_negation()

    def is_connector(self) -> bool:
        """Determines if a token is a connector (AND or OR)."""
        return self.is_connector_and() or self.is_connector_or()

    def is_connector_and(self) -> bool:
        """Determines if a token is an AND connector."""
        return self.kind == TokenKind.CONNECTOR_AND

    def is_connector_or(self) -> bool:
        """Determines if a token is an OR connector."""
        return self.kind == TokenKind.CONNECTOR_OR

    def is_negation(self) -> bool:
        """Determines if a token is a NOT negation."""
        return self.kind == TokenKind.NEGATION_NOT

    def is_paren(self) -> bool:
        """Determines if a token is a parenthesis."""
        return self.is_open_paren() or self.is_close_paren()

    def is_open_paren(self) -> bool:
        """Determines if a token is an open parenthesis."""
        return self.kind == TokenKind.OPEN_PARENTHESIS

    def is_close_paren(self) -> bool:
        """Determines if a token is a close parenthesis."""
        return self.kind == TokenKind.CLOSE_PARENTHESIS

    def is_subject(self) -> bool:
        """Determines if a token is a subject (a word or a quoted string)."""
        return self.kind == TokenKind.SUBJECT


def tokenize_expression(query: str) -> list[Token]:
    """
    Tokenizes a search query into a list of Token objects.

    Each token represents a word or symbol in the query,
    including subjects, connectors or parentheses.
    Consecutive double quotes are normalized to 1 double quote.

    Parameters
    ----------
    query : str
        The boolean search expression to tokenize.

    Returns
    -------
    list[Token]
        A list of Token objects representing the tokenized elements
        of the search query.

    Examples
    --------
    >>> tokenize_expression('(virus AND bacteria)')
    [Token('(', TokenKind.OPEN_PARENTHESIS),
     Token('virus', TokenKind.SUBJECT),
     Token('AND'. TokenKind.CONNECTOR_AND),
     Token('bacteria', TokenKind.SUBJECT),
     Token(')', TokenKind.CLOSE_PARENTHESIS)]
    """

    query = re.sub(r'"+', '"', query)

    PARENTHESIS = ["(", ")"]
    DOUBLE_QUOTES = '"'
    SINGLE_QUOTES = "'"

    tokens = []
    current_item = ""
    in_quotes = False
    subject = ""

    for char in query:
        if in_quotes:
            # in_quotes we consider every char as part of a subject
            subject += char
            if char == DOUBLE_QUOTES:
                tokens.append(
                    Token(
                        subject,
                        kind=TOKEN_MAP.get(char.upper(), TokenKind.SUBJECT),
                    )
                )
                subject = ""
                in_quotes = False
        elif char == DOUBLE_QUOTES:
            in_quotes = True
            subject += char
        elif char in PARENTHESIS:
            # parenthesis can be "glued" to another chars
            # so we just add it as a token
            if current_item:
                tokens.append(
                    Token(
                        current_item,
                        kind=TOKEN_MAP.get(
                            current_item.upper(), TokenKind.SUBJECT
                        ),
                    )
                )
                current_item = ""
            tokens.append(
                Token(
                    char,
                    kind=TOKEN_MAP.get(char.upper(), TokenKind.SUBJECT),
                )
            )
        elif char == SINGLE_QUOTES:
            continue
        elif char.isspace():
            # whitespace are ignored but represents the end of a token
            if current_item:
                tokens.append(
                    Token(
                        current_item,
                        kind=TOKEN_MAP.get(
                            current_item.upper(), TokenKind.SUBJECT
                        ),
                    )
                )
                current_item = ""
        else:
            current_item += char

    if current_item:
        tokens.append(
            Token(
                current_item,
                kind=TOKEN_MAP.get(current_item.upper(), TokenKind.SUBJECT),
            )
        )
    elif subject:
        tokens.append(
            Token(
                subject, kind=TOKEN_MAP.get(subject.upper(), TokenKind.SUBJECT)
            )
        )
    return tokens


def validate_expression(
    tokens: list[Token],
) -> tuple[bool, Optional[ExpressionValidationError]]:
    """
    Validates the syntactical correctness of a tokenized search expression.

    This function checks the sequence and balance of connectors, parentheses,
    and negations in the tokenized expression. It ensures that the query adheres
    to the logical structure expected for a search engine or database.

    Parameters
    ----------
    tokens : list[Token]
        A list of tokens representing the search expression.

    Returns
    -------
    tuple[bool, Optional[ExpressionValidationError]]
        A tuple where the first element is a boolean indicating the validity of
        the expression and the second element is an optional error message. If
        the expression is valid, the error message is None.

    Raises
    ------
    LogicalOperatorError
        Raised if there is an invalid sequence of operators.
    UnmatchedParenthesesError
        Raised if parentheses are not properly matched.
    UnmatchedQuotesError
        Raised if quotes are not properly closed.
    EmptyParenthesisError
        Raised if empty parentheses are found.
    ExpressionValidationError
        General validation error for incorrect token sequences.

    Examples
    --------
    >>> tokens = [Token('virus', TokenKind.SUBJECT), Token('AND', TokenKind.CONNECTOR_AND)]
    >>> validate_expression(tokens)
    (True, None)

    >>> tokens = [Token('AND', TokenKind.CONNECTOR_AND), Token('virus', TokenKind.SUBJECT)]
    >>> validate_expression(tokens)
    (False, LogicalOperatorError("Connector 'AND' can't start a query"))
    """
    paren_stack = []

    # if there is no tokens, get out
    if not tokens:
        return (
            False,
            EmptyQueryError("Empty query provided."),
        )

    # if number of quotes are not even, get out
    if not " ".join([token.value for token in tokens]).count('"') % 2 == 0:
        return (
            False,
            UnmatchedQuotesError(
                "Unmatched quotes found. Please, make sure all quotes are matched."
            ),
        )

    # loop trough each token in tokens list
    for i, token in enumerate(tokens):
        next_token = tokens[i + 1] if i < len(tokens) - 1 else None

        # handle parenthesis
        if token.is_paren():
            # handle open parenthesis
            if token.is_open_paren():
                paren_stack.append(token)
                if next_token and next_token.is_close_paren():
                    return (
                        False,
                        EmptyParenthesisError(
                            "Empty parenthesis '()' not allowed."
                        ),
                    )
                # open_paren can only be followed
                # by open_paren, subject or negation
                if next_token and not (
                    next_token.is_open_paren()
                    or next_token.is_subject()
                    or next_token.is_negation()
                ):
                    return (
                        False,
                        LogicalOperatorError(
                            f"Invalid operator sequence: '{token.value}' can't precede {next_token.value}"
                        ),
                    )

            # handle close parenthesis
            if token.is_close_paren():
                # when a close paren is found check if paren_stack matches
                # case stack is empty, this close_paren is illegal
                if not paren_stack:
                    return (
                        False,
                        UnmatchedParenthesesError(
                            "Unmatched closing parenthesis found."
                        ),
                    )
                paren_stack.pop()
                # close_paren can only be followed by
                # close_paren, connectors and negation
                if next_token and not (
                    next_token.is_close_paren() or next_token.is_keyword()
                ):
                    return (
                        False,
                        LogicalOperatorError(
                            f"Invalid operator sequence: '{token.value}' can't precede '{next_token.value}'"
                        ),
                    )

        # handle connectors
        if token.is_connector():
            # connectors can't start a query
            if i == 0:
                return (
                    False,
                    LogicalOperatorError(
                        f"Connector '{token.value}' can't start a query"
                    ),
                )
            # connectors can't end a query
            if i == len(tokens) - 1:
                return (
                    False,
                    LogicalOperatorError(
                        f"Connector '{token.value}' can't end a query"
                    ),
                )
            # connectors can only be followed by
            # subject or open_parens
            if next_token and not (
                next_token.is_subject() or next_token.is_open_paren()
            ):
                return (
                    False,
                    LogicalOperatorError(
                        f"Connector '{token.value}' can't precede {next_token.value}"
                    ),
                )

        # negation (NOT) rules
        if token.is_negation():
            # negation can't finish a query
            if i == len(tokens) - 1:
                return (
                    False,
                    LogicalOperatorError(
                        f"Invalid operator sequence: '{token.value}' can't end a query"
                    ),
                )
            # negation can only come before subject, quotes or open_paren
            if next_token and not (
                next_token.is_subject() or next_token.is_open_paren()
            ):
                return (
                    False,
                    LogicalOperatorError(
                        f"Invalid operator sequence: '{token.value}' can't precede {next_token.value}"
                    ),
                )

        if token.is_subject():
            if next_token and next_token.is_subject():
                return (
                    False,
                    ExpressionValidationError(
                        "Subject can't precede another subject"
                    ),
                )

            # subject can only be followed by
            # connector or close_paren
            if next_token and not (
                next_token.is_keyword() or next_token.is_close_paren()
            ):
                return (
                    False,
                    LogicalOperatorError(
                        f"Invalid operator sequence: search subject '{token.value}' precede {next_token.value}"
                    ),
                )

    # Final check for unclosed parenthesis
    if paren_stack:
        return (
            False,
            UnmatchedParenthesesError(
                "Unmatched opening parenthesis found. Please, make sure all parenthesis are matched."
            ),
        )

    return True, None


def parse_expression(tokens: list[Token]) -> str:
    """
    Converts a list of tokens from a boolean search query into a query string.

    This function interprets each token and assembles them into a structured
    query string. It adds '+' symbols as necessary to denote logical
    connections between the elements of the query. The output is formatted
    for use in a search system.

    Parameters
    ----------
    tokens : list[Token]
        A list of tokens representing the boolean search query.

    Returns
    -------
    str
        A string representing the parsed boolean search query, where elements
        are separated by '+' symbols.

    Examples
    --------
    >>> tokens = [Token('virus', TokenKind.SUBJECT), Token('AND', TokenKind.CONNECTOR_AND), Token('bacteria', TokenKind.SUBJECT)]
    >>> parse_expression(tokens)
    'virus+AND+bacteria+'
    """
    query: list[str] = []

    for i, token in enumerate(tokens):
        next_token = tokens[i + 1] if i < len(tokens) - 1 else None

        if (
            token.is_subject() or token.is_keyword() or token.is_close_paren()
        ) and (next_token and not next_token.is_close_paren()):
            query.append(f"{token.value}+")
        else:
            query.append(token.value)

    # Add the final '+' at the end of the expression
    if query and not query[-1].endswith("+"):
        query.append("+")

    return "".join(query)


def process_search_query(
    search_query: str,
) -> tuple[str, tuple[bool, Optional[ExpressionValidationError]]]:
    """
    Processes a boolean search query string through tokenization, validation,
    and parsing.

    This function first breaks down the query string into tokens. It then
    validates these tokens to ensure the query's syntactical correctness.
    Finally, it parses the validated tokens into a structured query string
    suitable for a search system. If validation fails, it provides relevant
    error information.

    Parameters
    ----------
    search_query : str
        The boolean search query string to be processed.

    Returns
    -------
    tuple[str, tuple[bool, Optional[ExpressionValidationError]]]
        A tuple where the first element is the parsed query string (empty if
        validation fails) and the second element is another tuple indicating
        the validation status and any associated error message.

    Examples
    --------
    >>> process_search_query('"virus vitamin" AND telemedicine OR (water AND "good wine")')
    ('"virus vitamin"+AND+telemedicine+OR+(water+AND+"good wine")+', (True, None))
    """
    tokens = tokenize_expression(search_query)

    is_valid, exception = validate_expression(tokens)

    parsed_query = parse_expression(tokens)

    return parsed_query, (is_valid, exception)


@dataclass
class Node:
    """
    A base class representing a node in an abstract syntax tree.

    Attributes
    ----------
    left : Optional[Node], default=None
        The left child node.
    right : Optional[Node], default=None
        The right child node.
    child : Optional[Node], default=None
        The single child node, used in unary operations like NOT.
    value : Optional[Any], default=None
        The value stored in the node, typically used in leaf nodes.

    Methods
    -------
    is_or_node() -> bool
        Check if the node is an OrNode.
    is_and_node() -> bool
        Check if the node is an AndNode.
    is_not_node() -> bool
        Check if the node is a NotNode.
    is_subject_node() -> bool
        Check if the node is a SubjectNode.
    to_dict() -> dict[str, Any]
        Convert the node to a dictionary representation.
    """

    left: Optional["Node"] = None
    right: Optional["Node"] = None
    child: Optional["Node"] = None
    value: Optional[Any] = None

    def is_or_node(self) -> bool:
        """Check if the node is an OrNode."""
        return isinstance(self, OrNode)

    def is_and_node(self) -> bool:
        """Check if the node is an AndNode."""
        return isinstance(self, AndNode)

    def is_not_node(self) -> bool:
        """Check if the node is a NotNode."""
        return isinstance(self, NotNode)

    def is_subject_node(self) -> bool:
        """Check if the node is a SubjectNode."""
        return isinstance(self, SubjectNode)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the node to a dictionary representation.

        This method must be implemented in subclasses.
        """
        raise NotImplementedError("Must be implemented in subclass")

    def __str__(self) -> str:
        """
        Return a string representation of the node.

        Returns
        -------
        str
            A string representation of the node.
        """
        return pformat({"root": self.to_dict()})


@dataclass
class AndNode(Node):
    """
    Represents a logical AND node in the abstract syntax tree.

    Inherits from Node and uses left and right attributes to represent
    the operands of the AND operation.

    Methods
    -------
    to_dict() -> dict[str, Any]
        Convert the AndNode to a dictionary representation.
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the AndNode to a dictionary representation.

        Returns
        -------
        dict[str, Any]
            A dictionary with 'AndNode' as the key and a dict of its children
            as the value.
        """
        return {
            "AndNode": {
                "left": self.left.to_dict() if self.left else None,
                "right": self.right.to_dict() if self.right else None,
            }
        }


@dataclass
class OrNode(Node):
    """
    Represents a logical OR node in the abstract syntax tree.

    Inherits from Node and uses left and right attributes to represent
    the operands of the OR operation.

    Methods
    -------
    to_dict() -> dict[str, Any]
        Convert the OrNode to a dictionary representation.
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the OrNode to a dictionary representation.

        Returns
        -------
        dict[str, Any]
            A dictionary with 'OrNode' as the key and a dict of its children
            as the value.
        """
        return {
            "OrNode": {
                "left": self.left.to_dict() if self.left else None,
                "right": self.right.to_dict() if self.right else None,
            }
        }


@dataclass
class NotNode(Node):
    """
    Represents a logical NOT node in the abstract syntax tree.

    Inherits from Node and uses the child attribute to represent
    the operand of the NOT operation.

    Methods
    -------
    to_dict() -> dict[str, Any]
        Convert the NotNode to a dictionary representation.
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the NotNode to a dictionary representation.

        Returns
        -------
        dict[str, Any]
            A dictionary with 'NotNode' as the key and a dict of its child
            as the value.
        """
        return {
            "NotNode": {"child": self.child.to_dict() if self.child else None}
        }


@dataclass
class SubjectNode(Node):
    """
    Represents a subject or a term node in the abstract syntax tree.

    Inherits from Node and uses the value attribute to represent
    the term itself.

    Methods
    -------
    to_dict() -> dict[str, Any]
        Convert the SubjectNode to a dictionary representation.
    """

    value: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the SubjectNode to a dictionary representation.

        Returns
        -------
        dict[str, Any]
            A dictionary with 'SubjectNode' as the key and the subject value.
        """
        return {"SubjectNode": {"value": self.value}}


class Parser:
    """
    A parser for converting a list of tokens into an abstract syntax tree (AST).

    This class encapsulates the functionality required to parse tokens generated
    from a search query and construct an AST that represents the logical structure
    of the query. This AST can then be used for further processing, such as
    generating a query for a search engine like Elasticsearch.

    Parameters
    ----------
    tokens : list[Token]
        A list of tokens to be parsed into an AST. Tokens are typically generated
        by tokenizing a search query string.

    Attributes
    ----------
    ast_root : Node
        The root node of the AST generated by parsing the tokens. This attribute
        is populated after calling the `parse` method.
    tokens : list[Token]
        The list of tokens that the parser will process to generate an AST.

    Methods
    -------
    parse() -> Node
        Parses the tokens provided to the class and constructs an AST. This method
        initializes the `ast_root` attribute with the root node of the AST.

    Notes
    -----
    The `Parser` class utilizes a recursive descent parsing approach, supporting
    basic logical operators such as AND, OR, and NOT, and handling precedence
    and parentheses appropriately.

    Examples
    --------
    >>> tokens = tokenize_expression('virus AND bacteria')
    >>> parser = Parser(tokens)
    >>> ast_root = parser.parse()
    >>> print(ast_root)
    AndNode(left=SubjectNode(value='virus'), right=SubjectNode(value='bacteria'))
    """

    ast_root: Node
    tokens: list[Token]

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens

    def parse(self) -> Node:
        """Parse tokens into an abstract syntax tree (AST).

        This method orchestrates the parsing of the provided tokens into an AST
        by calling the `parse_tokens_to_ast` method and setting the `ast_root`
        attribute with the result.

        Returns
        -------
        Node
            The root node of the generated AST.

        Examples
        --------
        >>> tokens = tokenize_expression('virus AND bacteria')
        >>> parser = Parser(tokens)
        >>> ast_root = parser.parse()
        >>> isinstance(ast_root, AndNode)
        True
        """
        self.ast_root = self.parse_tokens_to_ast(self.tokens)
        return self.ast_root

    def parse_tokens_to_ast(self, tokens: list[Token]) -> Node:
        """
        Parse a list of tokens into an abstract syntax tree (AST).

        Parameters
        ----------
        tokens : list[Token]
            A list of Token objects representing the parsed query.

        Returns
        -------
        Node
            The root node of the constructed abstract syntax tree.

        Notes
        -----
        This function constructs the AST by recursively parsing expressions,
        handling precedence of operations and parentheses.
        """

        return self.parse_expression(self.tokens)

    def parse_expression(
        self, tokens: list[Token], start: int = 0, end: Optional[int] = None
    ) -> Node:
        """
        Parse a sublist of tokens into a sub-AST.

        Parameters
        ----------
        tokens : list[Token]
            The list of tokens to parse.
        start : int, optional
            The starting index in the token list from which to begin parsing.
        end : Optional[int], optional
            The ending index in the token list at which to stop parsing. If None,
            parsing continues to the end of the list.

        Returns
        -------
        Node
            The root node of the constructed sub-AST for the given token sublist.

        Notes
        -----
        This function is a helper function used within `parse_tokens_to_ast` to
        handle recursive parsing of nested expressions within parentheses.
        """
        if end is None:
            end = len(tokens)

        current_node = None
        i = start
        while i < end:
            token = tokens[i]

            if token.is_subject():
                new_node = SubjectNode(value=token.value)
                current_node = self.combine_nodes(current_node, new_node)

            elif token.is_connector_and():
                # Ensure current node is an AndNode, or wrap it in an AndNode
                current_node = self.ensure_and_node(current_node)

            elif token.is_connector_or():
                # Ensure current node is an OrNode, or wrap it in an OrNode
                current_node = self.ensure_or_node(current_node)

            elif token.is_negation():
                # Parse the expression after `NOT` and wrap it in `NotNode`
                if tokens[i + 1].is_open_paren():
                    close_idx = self.find_matching_paren(tokens, i + 1)
                    negated_expression = self.parse_expression(
                        tokens, i + 2, close_idx
                    )
                    i = close_idx  # Skip past the closing parenthesis
                else:
                    negated_expression = SubjectNode(value=tokens[i + 1].value)
                    i += 1  # Skip the next token (subject after `NOT`)

                current_node = self.combine_nodes(
                    current_node, NotNode(child=negated_expression)
                )

            elif token.is_open_paren():
                close_idx = self.find_matching_paren(tokens, i)
                sub_expression = self.parse_expression(
                    tokens, i + 1, close_idx
                )
                current_node = self.combine_nodes(current_node, sub_expression)
                i = close_idx  # Skip past the closing parenthesis

            i += 1

        return current_node  # type: ignore

    def combine_nodes(
        self, current_node: Optional[Node], new_node: Node
    ) -> Node:
        """
        Combine two AST nodes according to the rules of precedence and association.

        Parameters
        ----------
        current_node : Optional[Node]
            The current node in the AST being constructed. May be None if the AST is empty.
        new_node : Node
            The new node to be added to the AST.

        Returns
        -------
        Node
            The resulting node after combining `current_node` and `new_node`.

        Notes
        -----
        This function ensures that AND and OR operations are properly associated
        and that NOT operations are correctly applied. It also handles the creation
        of new AndNode or OrNode instances as needed to maintain the correct structure
        of the AST.
        """
        if current_node is None:
            return new_node
        elif current_node.is_or_node():
            # If the current node is an OrNode, continue the OR chain
            if current_node.right is None:
                current_node.right = new_node  # If right child is empty, simply add the new node
            else:
                # If the right child is occupied, create a new OrNode with the current OrNode as the left child
                current_node = OrNode(left=current_node, right=new_node)
        elif current_node.is_and_node() or current_node.is_not_node():
            # If the current node is an AndNode or NotNode and the right child is empty, add the new node
            if current_node.right is None:
                current_node.right = new_node
            else:
                # If the right child is occupied, create a new AndNode
                current_node = AndNode(left=current_node, right=new_node)
        else:
            # If the current node is a SubjectNode or an unrecognized type, create a new AndNode
            current_node = AndNode(left=current_node, right=new_node)
        return current_node

    def ensure_and_node(self, current_node: Optional[Node]) -> Node:
        """
        Ensure that the given node is an AndNode.

        Parameters
        ----------
        current_node : Optional[Node]
            The node to be ensured as an AndNode.

        Returns
        -------
        Node
            An AndNode that contains `current_node` as its left child if `current_node`
            is not already an AndNode; otherwise, `current_node` itself.

        Notes
        -----
        This function is used to maintain the precedence of AND operations in the AST.
        If the `current_node` is not an AndNode, a new AndNode is created with
        `current_node` as its left child.
        """
        if (
            current_node is None or not current_node.is_and_node()
        ):  # not isinstance(current_node, AndNode):
            return AndNode(left=current_node, right=None)
        return current_node

    def ensure_or_node(self, current_node: Optional[Node]) -> Node:
        """
        Ensure that the given node is an OrNode.

        Parameters
        ----------
        current_node : Optional[Node]
            The node to be ensured as an OrNode.

        Returns
        -------
        Node
            An OrNode that contains `current_node` as its left child if `current_node`
            is not already an OrNode; otherwise, `current_node` itself.

        Notes
        -----
        This function is used to maintain the precedence of OR operations in the AST.
        If the `current_node` is not an OrNode, a new OrNode is created with
        `current_node` as its left child.
        """
        if (
            current_node is None or not current_node.is_or_node()
        ):  # isinstance(current_node, OrNode):
            return OrNode(left=current_node, right=None)
        return current_node

    def find_matching_paren(self, tokens: list[Token], open_idx: int) -> int:
        """
        Find the index of the matching closing parenthesis.

        Given the index of an open parenthesis in a list of tokens,
        this function finds the corresponding closing parenthesis.

        Parameters
        ----------
        tokens : list[Token]
            A list of Token objects representing the parsed query.
        open_idx : int
            The index of the open parenthesis in the tokens list.

        Returns
        -------
        int
            The index of the corresponding closing parenthesis.

        Raises
        ------
        ValueError
            If no matching closing parenthesis is found.

        Notes
        -----
        This function uses a stack-based approach to match parentheses,
        accounting for nested structures.
        """
        stack = 1
        for i in range(open_idx + 1, len(tokens)):
            if tokens[i].is_open_paren():
                stack += 1
            elif tokens[i].is_close_paren():
                stack -= 1
                if stack == 0:
                    return i
        raise ValueError("No matching closing parenthesis found.")


class ElasticSearchQueryBuilder:
    """
    A class for building Elasticsearch queries from an Abstract Syntax Tree (AST).

    This class facilitates the conversion of an AST, representing the structured
    format of a search query, into a query that Elasticsearch can execute. The
    conversion process involves translating various AST node types (e.g., subject,
    AND, OR, NOT) into their corresponding Elasticsearch query components.

    Parameters
    ----------
    ast_root : Optional[Node]
        The root node of the abstract syntax tree to be converted. If `None`, an
        empty Elasticsearch query is generated by default.

    Attributes
    ----------
    ast_root : Node, optional
        The root node of the AST from which the Elasticsearch query is built.

    Methods
    -------
    build_query() -> dict[str, Any]
        Constructs and returns the Elasticsearch DSL (Domain Specific Language) query
        from the AST root node.

    ast_to_elasticsearch(node: Optional[Node]) -> dict[str, Any]
        Converts an AST node and its children to the equivalent Elasticsearch query
        structure.

    flatten_conditions(conditions: list[dict[str, Any]], clause_type: str) -> list[dict[str, Any]]
        Optimizes the Elasticsearch query by merging conditions of the same type to
        reduce unnecessary nesting in the query structure.

    Examples
    --------
    >>> parser = Parser(tokenize_expression("(virus OR bacteria) NOT Brazil"))
    >>> ast_root = parser.parse()
    >>> query_builder = ElasticSearchQueryBuilder(ast_root)
    >>> es_query = query_builder.build_query()
    >>> print(es_query)
    {'query': {'bool': {'must': [{'bool': {'should': [{'multi_match': {'query': 'virus', 'fields': ['title', 'abstract']}}, {'multi_match': {'query': 'bacteria', 'fields': ['title', 'abstract']}}]}}, {'bool': {'must_not': [{'multi_match': {'query': 'Brazil', 'fields': ['title', 'abstract']}}]}}]}}}
    """

    ast_root: Optional[Node] = None

    def __init__(self, ast_root: Optional[Node]) -> None:
        """
        Initializes the ElasticSearchQueryBuilder with an optional AST root node.

        If an AST root node is provided, it will be used as the basis for building
        the Elasticsearch query. If `None`, an empty query will be generated.
        """
        self.ast_root = ast_root

    def build_query(self) -> dict[str, Any]:
        """Return the elastic search DSL query"""
        es_query = self.ast_to_elasticsearch(self.ast_root)
        es_query = self.adjust_conditions(es_query)

        return es_query

    def ast_to_elasticsearch(self, node: Optional[Node]) -> dict[str, Any]:
        """
        Recursively convert an AST node to its equivalent Elasticsearch query representation.

        Parameters
        ----------
        node : Optional[Node]
            The root node of the AST to be converted.

        Returns
        -------
        dict[str, Any]
            The Elasticsearch query represented as a dictionary.

        Notes
        -----
        This function recursively processes the AST, converting each node type
        to its corresponding part in an Elasticsearch query. It handles
        subject, AND, OR, and NOT nodes, translating them into match, must,
        should, and must_not clauses respectively.
        """
        query_clause: dict[str, Any] = {"bool": {}}

        if node is None:
            return query_clause
        else:
            if node.is_subject_node() and node.value:
                search_term = node.value.strip('"')

                if '"' in node.value:
                    subject_query = {
                        "bool": {
                            "should": [
                                {
                                    "match_phrase": {
                                        "document_text": search_term
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                else:
                    subject_query = {
                        "multi_match": {
                            "query": search_term,
                            "fields": ["document_text"],
                        }
                    }

                return subject_query

            elif node.is_and_node():
                must_conditions = [
                    self.ast_to_elasticsearch(node.left),
                    self.ast_to_elasticsearch(node.right),
                ]
                if must_conditions:
                    query_clause["bool"]["must"] = self.flatten_conditions(
                        must_conditions, "must"
                    )

            elif node.is_or_node():
                should_conditions = [
                    self.ast_to_elasticsearch(node.left),
                    self.ast_to_elasticsearch(node.right),
                ]
                if should_conditions:
                    query_clause["bool"]["should"] = self.flatten_conditions(
                        should_conditions, "should"
                    )

            elif node.is_not_node():
                must_not_conditions = [self.ast_to_elasticsearch(node.child)]
                if must_not_conditions:
                    query_clause["bool"]["must_not"] = must_not_conditions

            return query_clause

    def adjust_conditions(
        self, query: dict[str, Any], check_single_topic: bool = True
    ) -> dict[str, Any]:
        """
        Adjust the Elasticsearch query by moving 'must_not' clauses to the correct level.

        Parameters
        ----------
        query : dict[str, Any]
            The Elasticsearch query to be adjusted.

        Returns
        -------
        dict[str, Any]
            The adjusted Elasticsearch query.
        """
        if (
            check_single_topic
            and not "bool" in query
            and "multi_match" in query
        ):
            match_clause = query["multi_match"]
            query["bool"] = {"must": [{"multi_match": match_clause}]}
            del query["multi_match"]

        if "bool" in query and "should" in query["bool"]:
            # Traverse the 'should' clauses
            for should_clause in query["bool"]["should"]:
                if (
                    "bool" in should_clause
                    and "must_not" in should_clause["bool"]
                ):
                    # Move 'must_not' to a sibling of its parent expression
                    query["bool"]["must_not"] = should_clause["bool"][
                        "must_not"
                    ]
                    # Remove 'must_not' from its original position
                    del should_clause["bool"]["must_not"]

                    # If the 'should' clause is now empty, remove it
                    if not should_clause["bool"]:
                        query["bool"]["should"].remove(should_clause)

        # Recursively adjust sub-queries
        if isinstance(query, dict):
            for key, value in query.items():
                if isinstance(value, dict):
                    query[key] = self.adjust_conditions(value, False)
                elif isinstance(value, list):
                    query[key] = [
                        self.adjust_conditions(item, False) for item in value
                    ]

        return query

    def flatten_conditions(
        self, conditions: list[dict[str, Any]], clause_type: str
    ) -> list[dict[str, Any]]:
        """
        Flatten a list of Elasticsearch query conditions to avoid unnecessary nesting.

        Parameters
        ----------
        conditions : list[dict[str, Any]]
            A list of Elasticsearch query conditions, each represented as a dictionary.
        clause_type : str
            The type of clause ('must', 'should', or 'must_not') to be flattened.

        Returns
        -------
        list[dict[str, Any]]
            A flattened list of conditions.

        Notes
        -----
        This function is used to optimize the Elasticsearch query by merging
        conditions of the same type into a single list, reducing the depth
        of the query structure.
        """
        flattened = []
        for condition in conditions:
            if clause_type in condition.get("bool", {}):
                # Merge conditions of the same type from child into the parent
                flattened.extend(condition["bool"][clause_type])
            else:
                flattened.append(condition)
        return flattened


def process_search_query_elasticsearch(
    search_query: str, start_date: datetime.date, end_date: datetime.date
) -> dict[str, Any]:
    """
    Process a search query and convert it into an Elasticsearch query with date filters.

    This function takes a search query string, tokenizes it, parses it into an
    abstract syntax tree (AST), and then builds an Elasticsearch query from the AST.
    Additionally, it applies a date range filter to the query based on the provided
    start and end dates.

    Parameters
    ----------
    search_query : str
        The search query string to be processed.
    start_date : datetime.date
        The start date for the date range filter.
    end_date : datetime.date
        The end date for the date range filter.

    Returns
    -------
    dict[str, Any]
        The Elasticsearch query as a dictionary, including the query constructed
        from the search query string and the date range filter.

    Examples
    --------
    >>> search_query = "virus AND (bacteria OR cell) NOT host:human"
    >>> start_date = datetime.date(2020, 1, 1)
    >>> end_date = datetime.date(2021, 12, 31)
    >>> es_query = process_search_query_elasticsearch(search_query, start_date, end_date)
    >>> print(es_query)
    {
        'query': {
            'bool': {
                'must': [...],  # Query derived from `search_query`
                'filter': [{
                    'range': {
                        'decision_date': {
                            'gte': '2020-01-01',
                            'lte': '2021-12-31'
                        }
                    }
                }]
            }
        }
    }

    Notes
    -----
    The function uses `Parser` to parse the search query into an AST and
    `ElasticSearchQueryBuilder` to build the Elasticsearch query from the AST.
    The date range filter is added to the query to restrict the search results
    to documents within the specified date range.
    """
    tokens = tokenize_expression(search_query)

    ast_root = Parser(tokens).parse()
    es_query_builder = ElasticSearchQueryBuilder(ast_root)

    elastic_search_query = {"query": es_query_builder.build_query()}

    date_from = start_date.strftime("%Y-%m-%d")
    date_to = end_date.strftime("%Y-%m-%d")
    elastic_search_query["query"]["bool"]["filter"] = [
        {
            "range": {
                "decision_date": {
                    "gte": date_from,
                    "lte": date_to,
                }
            }
        }
    ]

    if "should" in elastic_search_query["query"]["bool"]:
        elastic_search_query["query"]["bool"]["minimum_should_match"] = 1

    return elastic_search_query


def extract_after_endroit(text: str) -> str:
    keyword = "EN DROIT"
    idx = text.find(keyword)
    if idx == -1:
        # Keyword not found: return entire document
        return text
    else:
        # Keyword found: return everything after the keyword
        # + len(keyword) to start *after* the phrase
        return text[idx + len(keyword) :].lstrip("\n")
