"""Unit tests for literev_core.boolean_query."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from literev_core.boolean_query import (
    PROMPT_TEMPLATE,
    convert_nl_to_boolean,
)


class TestPromptTemplate:
    """Tests for the PROMPT_TEMPLATE constant."""

    def test_prompt_contains_context_placeholder(self):
        """The template must contain the system prompt for LLM instructions."""
        assert "booléenne" in PROMPT_TEMPLATE

    def test_prompt_mentions_french(self):
        """The prompt must instruct the LLM to work in French."""
        assert "français" in PROMPT_TEMPLATE

    def test_prompt_mentions_boolean_operators(self):
        """The prompt must reference AND and OR operators (NOT is forbidden)."""
        assert "AND" in PROMPT_TEMPLATE
        assert "OR" in PROMPT_TEMPLATE
        assert "JAMAIS `NOT`" in PROMPT_TEMPLATE


class TestConvertNlToBoolean:
    """Tests for convert_nl_to_boolean function."""

    @patch("lr_query.boolean_query.litellm")
    def test_returns_stripped_string(self, mock_litellm):
        """The function should return a stripped string from the generator."""

        mock_response = MagicMock()
        mock_response.choices[0].message.content = " some boolean query "
        mock_litellm.completion.return_value = mock_response

        result = convert_nl_to_boolean(
            "Mon texte juridique",
            model_name="openai/mistral-small3.1:24b",
        )

        assert result == "some boolean query"

    @patch("lr_query.boolean_query.litellm")
    def test_passes_correct_params_to_hactar(self, mock_litellm):
        """Verify the function configures HactarLLM correctly."""

        # Create a fake litellm response object
        mock_response = MagicMock()
        mock_response.choices[0].message.content = " some boolean query "
        mock_litellm.completion.return_value = mock_response

        convert_nl_to_boolean(
            "test input",
            model_name="openai/mistral-small3.1:24b",
            base_url="http://legal-literev.unige.ch/hactar/api",
            api_key="test-key",
        )

        # check that mock_litellm was created with the right arguments
        mock_litellm.completion.assert_called_once_with(
            model="openai/mistral-small3.1:24b",
            messages=[
                {"role": "system", "content": PROMPT_TEMPLATE},
                {"role": "user", "content": "test input"},
            ],
            temperature=0,
            max_tokens=2048,
            api_base="http://legal-literev.unige.ch/hactar/api",
            api_key="test-key",
        )

    @patch("lr_query.boolean_query.litellm")
    def test_raises_runtime_error_on_failure(self, mock_litellm):
        """If the generator crashes, we should get a RuntimeError."""

        mock_litellm.completion.side_effect = ConnectionError("hactar is down")

        with pytest.raises(RuntimeError, match="Failed to convert"):
            convert_nl_to_boolean(
                "test", model_name="openai/mistral-small3.1:24b"
            )

    @patch("lr_query.boolean_query.litellm")
    def test_passes_text_to_generate(self, mock_litellm):
        """The user's input text must be passed to gen.generate() as context."""

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "result"
        mock_litellm.completion.return_value = mock_response

        convert_nl_to_boolean(
            "Quels sont les droits du locataire?",
            model_name="openai/mistral-small3.1:24b",
        )

        call_kwargs = mock_litellm.completion.call_args[1]
        user_messages = [
            m for m in call_kwargs["messages"] if m["role"] == "user"
        ]
        assert (
            user_messages[0]["content"]
            == "Quels sont les droits du locataire?"
        )
