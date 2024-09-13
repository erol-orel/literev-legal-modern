from datetime import datetime
from typing import List

from django.test import TestCase

from literev.libs import parsing


class TokenTestCase(TestCase):
    def setUp(self) -> None:
        self.token_subject = parsing.Token("amour", parsing.TokenKind.SUBJECT)
        self.token_and = parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND)
        self.token_or = parsing.Token("OR", parsing.TokenKind.CONNECTOR_OR)
        self.token_not = parsing.Token("NOT", parsing.TokenKind.NEGATION_NOT)
        self.token_open_paren = parsing.Token(
            "(", parsing.TokenKind.OPEN_PARENTHESIS
        )
        self.token_close_paren = parsing.Token(
            ")", parsing.TokenKind.CLOSE_PARENTHESIS
        )

    def test_is_keyword(self) -> None:
        self.assertTrue(self.token_and.is_keyword())
        self.assertTrue(self.token_or.is_keyword())
        self.assertTrue(self.token_not.is_keyword())
        self.assertFalse(self.token_subject.is_keyword())
        self.assertFalse(self.token_close_paren.is_keyword())
        self.assertFalse(self.token_open_paren.is_keyword())

    def test_is_connector(self) -> None:
        self.assertTrue(self.token_and.is_connector())
        self.assertTrue(self.token_or.is_connector())
        self.assertFalse(self.token_not.is_connector())
        self.assertFalse(self.token_close_paren.is_connector())
        self.assertFalse(self.token_open_paren.is_connector())
        self.assertFalse(self.token_subject.is_connector())

    def test_is_connector_and(self) -> None:
        self.assertTrue(self.token_and.is_connector_and())
        self.assertFalse(self.token_or.is_connector_and())
        self.assertFalse(self.token_not.is_connector_and())
        self.assertFalse(self.token_close_paren.is_connector_and())
        self.assertFalse(self.token_open_paren.is_connector_and())
        self.assertFalse(self.token_subject.is_connector_and())

    def test_is_connector_or(self) -> None:
        self.assertTrue(self.token_or.is_connector_or())
        self.assertFalse(self.token_and.is_connector_or())
        self.assertFalse(self.token_not.is_connector_or())
        self.assertFalse(self.token_close_paren.is_connector_or())
        self.assertFalse(self.token_open_paren.is_connector_or())
        self.assertFalse(self.token_subject.is_connector_or())

    def test_is_negation(self) -> None:
        self.assertTrue(self.token_not.is_negation())
        self.assertFalse(self.token_or.is_negation())
        self.assertFalse(self.token_and.is_negation())
        self.assertFalse(self.token_close_paren.is_negation())
        self.assertFalse(self.token_open_paren.is_negation())
        self.assertFalse(self.token_subject.is_negation())

    def test_is_paren(self) -> None:
        self.assertTrue(self.token_close_paren.is_paren())
        self.assertTrue(self.token_open_paren.is_paren())
        self.assertFalse(self.token_not.is_paren())
        self.assertFalse(self.token_or.is_paren())
        self.assertFalse(self.token_and.is_paren())
        self.assertFalse(self.token_subject.is_paren())

    def test_is_open_paren(self) -> None:
        self.assertTrue(self.token_open_paren.is_open_paren())
        self.assertFalse(self.token_close_paren.is_open_paren())
        self.assertFalse(self.token_not.is_open_paren())
        self.assertFalse(self.token_or.is_open_paren())
        self.assertFalse(self.token_and.is_open_paren())
        self.assertFalse(self.token_subject.is_open_paren())

    def test_is_close_paren(self) -> None:
        self.assertTrue(self.token_close_paren.is_close_paren())
        self.assertFalse(self.token_open_paren.is_close_paren())
        self.assertFalse(self.token_not.is_close_paren())
        self.assertFalse(self.token_or.is_close_paren())
        self.assertFalse(self.token_and.is_close_paren())
        self.assertFalse(self.token_subject.is_close_paren())

    def test_is_subject(self) -> None:
        self.assertTrue(self.token_subject.is_subject())
        self.assertFalse(self.token_close_paren.is_subject())
        self.assertFalse(self.token_open_paren.is_subject())
        self.assertFalse(self.token_not.is_subject())
        self.assertFalse(self.token_or.is_subject())
        self.assertFalse(self.token_and.is_subject())


class ParsingTestCase(TestCase):
    def setUp(self) -> None:
        pass

    def test_tokenize_expression_big_query(self) -> None:
        query = '((amour or marié) and (community or voiture)) and ((hospital or clinic) and "south america")'
        expected = [
            parsing.Token("(", kind=parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token("(", kind=parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token("amour", kind=parsing.TokenKind.SUBJECT),
            parsing.Token("or", kind=parsing.TokenKind.CONNECTOR_OR),
            parsing.Token("marié", kind=parsing.TokenKind.SUBJECT),
            parsing.Token(")", kind=parsing.TokenKind.CLOSE_PARENTHESIS),
            parsing.Token("and", kind=parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("(", kind=parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token("community", kind=parsing.TokenKind.SUBJECT),
            parsing.Token("or", kind=parsing.TokenKind.CONNECTOR_OR),
            parsing.Token("voiture", kind=parsing.TokenKind.SUBJECT),
            parsing.Token(")", kind=parsing.TokenKind.CLOSE_PARENTHESIS),
            parsing.Token(")", kind=parsing.TokenKind.CLOSE_PARENTHESIS),
            parsing.Token("and", kind=parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("(", kind=parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token("(", kind=parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token("hospital", kind=parsing.TokenKind.SUBJECT),
            parsing.Token("or", kind=parsing.TokenKind.CONNECTOR_OR),
            parsing.Token("clinic", kind=parsing.TokenKind.SUBJECT),
            parsing.Token(")", kind=parsing.TokenKind.CLOSE_PARENTHESIS),
            parsing.Token("and", kind=parsing.TokenKind.CONNECTOR_AND),
            parsing.Token('"south america"', kind=parsing.TokenKind.SUBJECT),
            parsing.Token(")", kind=parsing.TokenKind.CLOSE_PARENTHESIS),
        ]
        tokens = parsing.tokenize_expression(query)
        self.assertEqual(tokens, expected)

    def test_tokenize_expression_single_word(self) -> None:
        query = "dengue"
        expected = [parsing.Token("dengue", parsing.TokenKind.SUBJECT)]
        tokens = parsing.tokenize_expression(query)
        self.assertEqual(tokens, expected)

    def test_tokenize_expression_empty_query(self) -> None:
        query = " "
        expected: List[str] = []
        tokens = parsing.tokenize_expression(query)
        self.assertEqual(tokens, expected)

    def test_tokenize_expression_special_chars(self) -> None:
        query = " amour-mariage AND marié_infection"
        expected = [
            parsing.Token("amour-mariage", parsing.TokenKind.SUBJECT),
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("marié_infection", parsing.TokenKind.SUBJECT),
        ]
        tokens = parsing.tokenize_expression(query)
        self.assertEqual(tokens, expected)

    def test_validate_expression(self) -> None:
        queries = [
            "((amour or marié) and (community or voiture)) and (hospital or clinic)",
            '(randomized OR randomised) AND (clinical OR trial) AND (hospital OR healthcare OR voiture) AND (prevention OR control) AND (infection OR "antibiotic resistance") NOT (vacances OR therapy) NOT (retraite OR COVID OR malaria OR hepatitis OR tuberculosis) NOT ("community acquired")',
            '(randomized OR randomised) AND (clinical OR trial) AND (hospital OR healthcare OR voiture) AND (prevention OR control) AND (infection OR "antibiotic resistance")',
            "calmy[Author]",
            "mason AND (mali or nepal)",
            '("early retraite" OR "primary retraite" OR "acute retraite") AND africa',
            '"wastewater vacances" AND europe NOT chile',
        ]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, _ = parsing.validate_expression(tokens)
            self.assertTrue(is_valid)

    def test_validate_expression_empty_query(self) -> None:
        queries = ["", " "]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, exception = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)
            self.assertIsInstance(exception, parsing.EmptyQueryError)

    def test_validate_expression_missing_parenthesis(self) -> None:
        # missing parenthesis queries
        queries = [
            "(amour or marié) and (community or voiture)) and (hospital or clinic)",
            "((amour and marié and (community or voiture)) and (hospital or clinic)",
            "((amour and marié and (community or voiture)) and (hospital or clinic",
        ]

        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, exception = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)
            self.assertIsInstance(exception, parsing.UnmatchedParenthesesError)

    def test_validate_expression_empty_parentheses(self) -> None:
        query = "amour AND ()"
        tokens = parsing.tokenize_expression(query)
        is_valid, exception = parsing.validate_expression(tokens)
        self.assertFalse(is_valid)
        self.assertIsInstance(exception, parsing.EmptyParenthesisError)

    def test_validate_expression_missing_quotes(self) -> None:
        query = 'dengue and "south america'
        tokens = parsing.tokenize_expression(query)
        is_valid, exception = parsing.validate_expression(tokens)
        self.assertFalse(is_valid)
        self.assertIsInstance(exception, parsing.UnmatchedQuotesError)

    def test_validate_expression_consecutive_connectors(self) -> None:
        queries = [
            "amour AND OR marié",
            "amour OR OR marié",
            "amour OR AND marié",
            "amour NOT AND marié",
            "amour AND NOT marié",
            "amour OR NOT marié",
            "amour NOT OR marié",
            "amour NOT NOT marié",
        ]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, exception = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)
            self.assertIsInstance(exception, parsing.LogicalOperatorError)

    def test_validate_expression_connectors_at_start_or_end(self) -> None:
        queries = ["AND amour", "amour OR"]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, exception = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)
            self.assertIsInstance(exception, parsing.LogicalOperatorError)

    def test_validate_expression_correct_usage_of_not(self) -> None:
        valid_query = "NOT amour"
        invalid_query = "amour NOT"

        tokens = parsing.tokenize_expression(valid_query)
        is_valid, exception = parsing.validate_expression(tokens)
        self.assertTrue(is_valid)
        self.assertEqual(exception, None)

        tokens = parsing.tokenize_expression(invalid_query)
        is_valid, exception = parsing.validate_expression(tokens)
        self.assertFalse(is_valid)
        self.assertIsInstance(exception, parsing.LogicalOperatorError)

    def test_validate_expression_incorrect_usage_of_not(self) -> None:
        queries = [
            "amour NOT AND marié",
            "amour NOT OR marié",
            "NOT NOT amour",
            "amour AND NOT marié",
            "amour OR NOT marié",
        ]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, exception = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)
            self.assertIsInstance(exception, parsing.LogicalOperatorError)

    def test_validate_expression_adjacent_connector(self) -> None:
        queries = [
            "(amour AND marié)OR mariage",
            "amour AND(marié OR mariage)",
        ]
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            self.assertTrue(parsing.validate_expression(tokens))

    def test_validate_expression_query_not_before_paren(self) -> None:
        query = "NOT (amour OR marié)"
        tokens = parsing.tokenize_expression(query)
        self.assertTrue(parsing.validate_expression(tokens))

    def test_validate_expression_consecutive_subjects(self) -> None:
        queries = ["amour mariage", 'amour "south america"']
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, _ = parsing.validate_expression(tokens)
            self.assertFalse(is_valid)

    def test_validate_expression_reserved_words_as_subject(self) -> None:
        queries = ['"("', '"AND"', '"OR"', '"NOT"', '")"']
        for query in queries:
            tokens = parsing.tokenize_expression(query)
            is_valid, _ = parsing.validate_expression(tokens)
            self.assertTrue(is_valid)

    def test_is_subject_with_special_characters(self) -> None:
        query = "amour-mariage AND marié_infection"
        expected = [
            parsing.Token("amour-mariage", parsing.TokenKind.SUBJECT),
            parsing.Token("marié_infection", parsing.TokenKind.SUBJECT),
        ]
        tokens = parsing.tokenize_expression(query)
        subjects = [token for token in tokens if token.is_subject()]
        self.assertEqual(subjects, expected)

    def test_parse_expression(self) -> None:
        queries = [
            {
                "expression": '"amour" AND mason OR (water AND "good wine")',
                "expected": '"amour"+AND+mason+OR+(water+AND+"good wine")+',
            },
            {
                "expression": '((amour or marié) and (community or voiture)) and (hospital or clinic) and "south america"',
                "expected": '((amour+OR+marié)+AND+(community+OR+voiture))+AND+(hospital+OR+clinic)+AND+"south america"+',
            },
        ]
        for query in queries:
            tokens = parsing.tokenize_expression(query["expression"])
            parsing.validate_expression(tokens)
            result = parsing.parse_expression(tokens)
            self.assertEqual(result, query["expected"])

    def test_is_subject(self) -> None:
        query = 'amour AND (marié OR mariage) AND "south america"'
        tokens = parsing.tokenize_expression(query)
        result = [token.value for token in tokens if token.is_subject()]
        self.assertEqual(
            result, ["amour", "marié", "mariage", '"south america"']
        )

    def test_is_connector(self) -> None:
        query = 'amour AND (marié OR mariage) AND NOT "south america"'
        expected = [
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("OR", parsing.TokenKind.CONNECTOR_OR),
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
        ]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_connector()]
        self.assertEqual(result, expected)

    def test_is_negation(self) -> None:
        query = 'NOT amour AND (marié OR mariage) NOT "south america"'
        expected = [
            parsing.Token("NOT", parsing.TokenKind.NEGATION_NOT),
            parsing.Token("NOT", parsing.TokenKind.NEGATION_NOT),
        ]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_negation()]
        self.assertEqual(result, expected)

    def test_is_keyword(self) -> None:
        query = 'amour AND (marié OR mariage) NOT "south america"'
        expected = [
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("OR", parsing.TokenKind.CONNECTOR_OR),
            parsing.Token("NOT", parsing.TokenKind.NEGATION_NOT),
        ]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_keyword()]
        self.assertEqual(result, expected)

    def test_is_paren(self) -> None:
        query = 'amour AND (marié OR mariage) AND NOT "south america"'
        expected = [
            parsing.Token("(", parsing.TokenKind.OPEN_PARENTHESIS),
            parsing.Token(")", parsing.TokenKind.CLOSE_PARENTHESIS),
        ]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_paren()]
        self.assertEqual(result, expected)

    def test_is_open_paren(self) -> None:
        query = 'amour AND (marié OR mariage) AND NOT "south america"'
        expected = [parsing.Token("(", parsing.TokenKind.OPEN_PARENTHESIS)]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_open_paren()]
        self.assertEqual(result, expected)

    def test_is_close_paren(self) -> None:
        query = 'amour AND (marié OR mariage) AND NOT "south america"'
        expected = [parsing.Token(")", parsing.TokenKind.CLOSE_PARENTHESIS)]
        tokens = parsing.tokenize_expression(query)
        result = [token for token in tokens if token.is_close_paren()]
        self.assertEqual(result, expected)

    def test_single_quotes_outside_double_quotes(self) -> None:
        query = "amour AND 'marié' AND \"south 'america\""
        expected = [
            parsing.Token("amour", parsing.TokenKind.SUBJECT),
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
            parsing.Token("marié", parsing.TokenKind.SUBJECT),
            parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
            parsing.Token('"south \'america"', parsing.TokenKind.SUBJECT),
        ]
        tokens = parsing.tokenize_expression(query)
        self.assertEqual(tokens, expected)

    def test_consecutive_double_quotes(self) -> None:
        queries = [
            (
                'amour AND """vitamin c"""',
                [
                    parsing.Token("amour", parsing.TokenKind.SUBJECT),
                    parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
                    parsing.Token('"vitamin c"', parsing.TokenKind.SUBJECT),
                ],
            ),
            (
                'dengue AND ""vitamin c"" AND """"south america""""',
                [
                    parsing.Token("dengue", parsing.TokenKind.SUBJECT),
                    parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
                    parsing.Token('"vitamin c"', parsing.TokenKind.SUBJECT),
                    parsing.Token("AND", parsing.TokenKind.CONNECTOR_AND),
                    parsing.Token(
                        '"south america"', parsing.TokenKind.SUBJECT
                    ),
                ],
            ),
        ]

        for query, expected in queries:
            tokens = parsing.tokenize_expression(query)
            self.assertEqual(tokens, expected)

    def test_process_search_query(self) -> None:
        data = [
            {
                "query": '"amour vitamin" AND mason OR (water AND "good wine")',
                "expected": '"amour vitamin"+AND+mason+OR+(water+AND+"good wine")+',
            },
            {
                "query": 'dengue AND "south america" AND water',
                "expected": 'dengue+AND+"south america"+AND+water+',
            },
        ]

        for item in data:
            query = item["query"]
            output_expected = item["expected"]
            output_result, _ = parsing.process_search_query(query)
            self.assertEqual(output_result, output_expected)


class ParserTestCase(TestCase):
    def test_and_node(self) -> None:
        """Test if AndNode is created correctly"""
        query = "amour AND marié"
        expected_result = parsing.AndNode(
            left=parsing.SubjectNode(value="amour"),
            right=parsing.SubjectNode(value="marié"),
        )
        tokens = parsing.tokenize_expression(query)
        parser = parsing.Parser(tokens)
        result = parser.parse()

        self.assertEqual(result, expected_result)

    def test_or_node(self) -> None:
        """Test if OrNode is created correctly"""
        query = "(amour AND retraite) OR (marié AND vacances)"
        expected_result = parsing.OrNode(
            left=parsing.AndNode(
                left=parsing.SubjectNode(value="amour"),
                right=parsing.SubjectNode(value="retraite"),
            ),
            right=parsing.AndNode(
                left=parsing.SubjectNode(value="marié"),
                right=parsing.SubjectNode(value="vacances"),
            ),
        )
        tokens = parsing.tokenize_expression(query)
        parser = parsing.Parser(tokens)
        result = parser.parse()

        self.assertEqual(result, expected_result)

    def test_not_node(self) -> None:
        """Test if NotNode is created correctly"""
        query = "(retraite AND vacances) NOT mason"
        expected_result = parsing.AndNode(
            left=parsing.AndNode(
                left=parsing.SubjectNode(value="retraite"),
                right=parsing.SubjectNode(value="vacances"),
            ),
            right=parsing.NotNode(child=parsing.SubjectNode(value="mason")),
        )
        tokens = parsing.tokenize_expression(query)
        parser = parsing.Parser(tokens)
        result = parser.parse()

        self.assertEqual(result, expected_result)


class ElasticSearchTestCase(TestCase):
    DATE_FORMAT = "%Y-%m-%d"

    def test_process_search_elastic_search_and(self) -> None:
        """Test query with AND"""
        query = "amour AND marié"
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 12, 31)
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": "amour",
                                "fields": ["document_text"],
                            }
                        },
                        {
                            "multi_match": {
                                "query": "marié",
                                "fields": ["document_text"],
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_or(self) -> None:
        """Test query with OR"""
        query = "(amour AND marié) OR (retraite AND covid)"
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 12, 31)
        expected_result = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": "amour",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "marié",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": "retraite",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "covid",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )
        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_group_or_and(self) -> None:
        """Tests query with group of expressions with OR and AND"""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        query = (
            '("randomised clinical" OR "randomized clinical") '
            "AND (hospital OR healthcare OR voiture) "
            "AND (prevention OR control)"
        )
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase": {
                                            "document_text": "randomised clinical",
                                        }
                                    },
                                    {
                                        "match_phrase": {
                                            "document_text": "randomized clinical",
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "query": "hospital",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "healthcare",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "voiture",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "query": "prevention",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "control",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )
        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_not(self) -> None:
        """Tests query with NOT"""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        query = "NOT marié"
        expected_result = {
            "query": {
                "bool": {
                    "must_not": [
                        {
                            "multi_match": {
                                "query": "marié",
                                "fields": ["document_text"],
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_and_not(self) -> None:
        """Tests query with group of expressions with AND and NOT"""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        query = (
            "(influence OR apoptosis) AND (energy OR implications) NOT therapy"
        )
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "query": "influence",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "apoptosis",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "query": "energy",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "implications",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must_not": [
                                    {
                                        "multi_match": {
                                            "query": "therapy",
                                            "fields": ["document_text"],
                                        }
                                    }
                                ]
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_group_or_not(self) -> None:
        """Test query with group of expressions containing OR and NOT"""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        query = (
            "(energy AND implications) OR (influence AND apoptosis) NOT congo"
        )

        expected_result = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": "energy",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "implications",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                        {
                            "bool": {
                                "must": [
                                    {
                                        "multi_match": {
                                            "query": "influence",
                                            "fields": ["document_text"],
                                        }
                                    },
                                    {
                                        "multi_match": {
                                            "query": "apoptosis",
                                            "fields": ["document_text"],
                                        }
                                    },
                                ]
                            }
                        },
                    ],
                    "must_not": [
                        {
                            "multi_match": {
                                "query": "congo",
                                "fields": ["document_text"],
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Updated field name
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                    "minimum_should_match": 1,
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)

    def test_process_search_elastic_search_single_topic(self) -> None:
        """Test query with single topic"""
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        query = "divorce"
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": "divorce",
                                "fields": [
                                    "document_text"
                                ],  # Updated field name
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Updated field name
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)


class ElasticSearchComposedWordsTestCase(TestCase):
    DATE_FORMAT = "%Y-%m-%d"

    def test_single_word_using_and_in_document_text(self) -> None:
        """Test that a single word matches in either title or abstract."""
        query = "fever"
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": "fever",
                                "fields": [
                                    "document_text"
                                ],  # Ensure this field is correct
                            }
                        }
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Updated field name
                                    "gte": start_date.strftime(
                                        self.DATE_FORMAT
                                    ),
                                    "lte": end_date.strftime(self.DATE_FORMAT),
                                }
                            }
                        }
                    ],
                }
            }
        }

        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        self.assertEqual(result, expected_result)

    def test_composed_word_in_document_text(self) -> None:
        """Test that a composed word matches in the document_text field."""
        # Define the test parameters
        query = '"yellow fever"'
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)

        # Define the expected result
        expected_result = {
            "query": {
                "bool": {
                    "should": [
                        {"match_phrase": {"document_text": "yellow fever"}}
                    ],
                    "minimum_should_match": 1,
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Adjusted field name to 'decision_date'
                                    "gte": start_date.strftime("%Y-%m-%d"),
                                    "lte": end_date.strftime("%Y-%m-%d"),
                                }
                            }
                        }
                    ],
                }
            }
        }

        # Call the function under test
        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        # Assert that the result matches the expected result
        self.assertEqual(result, expected_result)

    def test_composed_words_using_and_in_document_text(self) -> None:
        """Test that multiple composed words match in the document_text field."""
        query = '"yellow fever" AND "climate change"'
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)

        # Define the expected result
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase": {
                                            "document_text": "yellow fever"
                                        }
                                    }
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                        {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase": {
                                            "document_text": "climate change"
                                        }
                                    }
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Updated field name to 'decision_date'
                                    "gte": start_date.strftime("%Y-%m-%d"),
                                    "lte": end_date.strftime("%Y-%m-%d"),
                                }
                            }
                        }
                    ],
                }
            }
        }

        # Call the function under test
        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        # Assert that the result matches the expected result
        self.assertEqual(result, expected_result)

    def test_composed_word_and_single_word_using_and_in_document_text(
        self,
    ) -> None:
        """Test that a composed word and a single word match in the document_text field."""
        query = '"yellow fever" AND mosquitoes'
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)

        # Define the expected result
        expected_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase": {
                                            "document_text": "yellow fever"
                                        }
                                    }
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                        {
                            "multi_match": {
                                "query": "mosquitoes",
                                "fields": ["document_text"],
                            }
                        },
                    ],
                    "filter": [
                        {
                            "range": {
                                "decision_date": {  # Updated field name to 'decision_date'
                                    "gte": start_date.strftime("%Y-%m-%d"),
                                    "lte": end_date.strftime("%Y-%m-%d"),
                                }
                            }
                        }
                    ],
                }
            }
        }

        # Call the function under test
        result = parsing.process_search_query_elasticsearch(
            query, start_date, end_date
        )

        # Assert that the result matches the expected result
        self.assertEqual(result, expected_result)
