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
        assert "Boolean" in PROMPT_TEMPLATE or "boolean" in PROMPT_TEMPLATE

    def test_prompt_mentions_french(self):
        """The prompt must instruct the LLM to work in French."""
        assert "French" in PROMPT_TEMPLATE

    def test_prompt_mentions_boolean_operators(self):
        """The prompt must reference AND, OR, NOT operators."""
        assert "AND" in PROMPT_TEMPLATE
        assert "OR" in PROMPT_TEMPLATE
        assert "NOT" in PROMPT_TEMPLATE


class TestConvertNlToBoolean:
    """Tests for convert_nl_to_boolean function."""

    @patch("literev_core.boolean_query.litellm")
    def test_returns_stripped_string(self, mock_litellm):
        """The function should return a stripped string from the generator."""

        mock_response = MagicMock()
        mock_response.choices[0].message.content = " some boolean query "
        mock_litellm.completion.return_value = mock_response

        result = convert_nl_to_boolean("Mon texte juridique")

        assert result == "some boolean query"

    @patch("literev_core.boolean_query.litellm")
    def test_passes_correct_params_to_ollama(self, mock_litellm):
        """Verify the function configures OllamaOpenAIGen correctly."""

        # Create a fake litellm response object
        mock_response = MagicMock()
        mock_response.choices[0].message.content = " some boolean query "
        mock_litellm.completion.return_value = mock_response

        convert_nl_to_boolean(
            "test input",
            model_name="mistral:7b",
            base_url="http://my-ollama:11434",
        )

        # check that mock_litellm was created with the right arguments
        mock_litellm.completion.assert_called_once_with(
            model="mistral:7b",
            messages=[
                {"role": "system", "content": PROMPT_TEMPLATE},
                {"role": "user", "content": "test input"},
            ],
            api_base="http://my-ollama:11434",
            temperature=0,
            max_tokens=2048,
        )

    @patch("literev_core.boolean_query.litellm")
    def test_raises_runtime_error_on_failure(self, mock_litellm):
        """If the generator crashes, we should get a RuntimeError."""

        mock_litellm.completion.side_effect = ConnectionError("Ollama is down")

        with pytest.raises(RuntimeError, match="Failed to convert"):
            convert_nl_to_boolean("test")

    @patch("literev_core.boolean_query.litellm")
    def test_passes_text_to_generate(self, mock_litellm):
        """The user's input text must be passed to gen.generate() as context."""

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "result"
        mock_litellm.completion.return_value = mock_response

        convert_nl_to_boolean("Quels sont les droits du locataire?")

        call_kwargs = mock_litellm.completion.call_args[1]
        user_messages = [
            m for m in call_kwargs["messages"] if m["role"] == "user"
        ]
        assert (
            user_messages[0]["content"]
            == "Quels sont les droits du locataire?"
        )
