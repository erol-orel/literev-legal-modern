"""Classes for augmentation with Hactar embeddings."""

from __future__ import annotations

import json
import logging

from hashlib import sha256
from typing import cast

import numpy as np
import requests

from django.conf import settings
from pydantic import BaseModel
from rago.augmented.base import AugmentedBase, EmbeddingType
from rago.generation.base import GenerationBase
from typeguard import typechecked

logger = logging.getLogger(__name__)

HACTAR_VERIFY_SSL = settings.HACTAR_VERIFY_SSL
REQUEST_TIMEOUT_S: int = 120


class HactarConnectionHelper:
    def check_hactar_api_connection(
        self, base_url: str, headers: dict, verify_ssl: bool = True
    ) -> None:
        """Test the connection to Hactar API."""
        try:
            response = requests.get(
                f"{base_url}/models",
                headers=headers,
                verify=verify_ssl,
                timeout=REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to connect to Hactar API: {e}")


@typechecked
class HactarAug(HactarConnectionHelper, AugmentedBase):
    """Class for augmentation with Hactar embeddings."""

    default_model_name = "mxbai-embed-large:latest"
    default_top_k = 3
    api_base_url = "https://hactar.unige.ch"

    def _setup(self) -> None:
        """Set up connection with initial parameters."""

        if not self.api_key:
            raise ValueError("API key for Hactar is required.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Test connection
        self.check_hactar_api_connection(
            self.api_base_url,
            self.headers,
            verify_ssl=HACTAR_VERIFY_SSL,
        )

    def get_embedding(self, content: list[str]) -> EmbeddingType:
        """Retrieve the embedding for a given text using Hactar API.
        \nSources:
        - https://docs.openwebui.com/getting-started/api-endpoints/
        - https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
        """

        self._REQUEST_TIMEOUT_S = 120

        cache_key = sha256("".join(content).encode("utf-8")).hexdigest()
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cast(EmbeddingType, cached)

        url = f"{self.api_base_url}/ollama/api/embed"
        data = {"model": self.model_name, "input": content}

        logger.info("Requesting embeddings from Hactar...")

        response = requests.post(
            url,
            headers=self.headers,
            json=data,
            verify=settings.HACTAR_VERIFY_SSL,
            timeout=self._REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        result_json = response.json()

        if "embeddings" not in result_json:
            raise ValueError(f"Unexpected API response format: {result_json}")

        result = np.array(result_json["embeddings"], dtype=np.float32)
        if result.ndim == 1:
            result = result.reshape(1, -1)

        self._save_cache(cache_key, result)

        return result

    def search(
        self, query: str, documents: list[str], top_k: int = 0
    ) -> list[str]:
        """Search an encoded query into vector database."""
        if not hasattr(self, "db") or not self.db:
            raise Exception("Vector database (db) is not initialized.")

        document_encoded = self.get_embedding(documents)
        query_encoded = self.get_embedding([query])
        top_k = top_k or self.top_k or self.default_top_k or 1

        self.db.embed(document_encoded)
        scores, indices = self.db.search(query_encoded, top_k=top_k)

        self.logs["indices"] = indices
        self.logs["scores"] = scores
        self.logs["search_params"] = {
            "query_encoded": query_encoded,
            "top_k": top_k,
        }

        logger.info(f"Confidence : {scores}")
        retrieved_docs = [documents[i] for i in indices if i >= 0]

        return retrieved_docs


@typechecked
class HactarGen(HactarConnectionHelper, GenerationBase):
    """API endpoint generation model for text generation."""

    default_model_name = "mistral-small3.1:24b"
    api_base_url = "https://hactar.unige.ch"
    default_api_params = {
        "top_p": 1.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    def _setup(self) -> None:
        """Set up connection with initial parameters."""
        if not self.api_key:
            raise ValueError("API key for Hactar is required.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Test connection
        self.check_hactar_api_connection(
            self.api_base_url,
            self.headers,
            verify_ssl=HACTAR_VERIFY_SSL,
        )

    def generate(self, query: str, context: list[str]) -> str | BaseModel:
        """Generate text using Ollama's API
        \nSources:
        - https://docs.openwebui.com/getting-started/api-endpoints/
        - https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion"""
        input_text = self.prompt_template.format(
            query=query, context=" ".join(context)
        )
        api_params = (
            self.api_params if self.api_params else self.default_api_params
        )

        if self.structured_output:
            messages = []

            system_instruction = (
                "Generate a JSON object that strictly follows the provided  "
                "JSON schema. Do not include any additional text."
            )

            if self.system_message:
                system_instruction += " " + self.system_message
            messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": input_text})

            model_params = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature or 0.0,
                    "top_p": api_params.get("top_p", 1.0),
                    "frequency_penalty": api_params.get(
                        "frequency_penalty", 0.0
                    ),
                    "presence_penalty": api_params.get(
                        "presence_penalty", 0.0
                    ),
                    "num_predict": self.output_max_length or 1024,
                },
                "format": self.structured_output.model_json_schema(),
            }

            logger.info(
                f"Requesting chat completion from Hactar... with following prompt : {messages}"
            )
            response = requests.post(
                f"{self.api_base_url}/ollama/api/chat",
                headers=self.headers,
                json=model_params,
                verify=settings.HACTAR_VERIFY_SSL,
            )
            response.raise_for_status()
            result = response.json()

            self.logs["model_params"] = model_params
            self.logs["raw_response"] = result

            logger.info(f"Response : {result.get('message')}")
            generation_speed = (
                result.get("eval_count") / result.get("eval_duration") * 10**9
            )
            logger.info(f"Token per second : {generation_speed}")

            try:
                content = result["message"]["content"].strip()
                parsed_dict = json.loads(content)
                return self.structured_output(**parsed_dict)
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse response: {e}")
                raise ValueError(f"Invalid response format: {result}")

        if self.system_message:
            messages = [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": input_text},
            ]
            model_params = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature or 0.0,
                    "top_p": api_params.get("top_p", 1.0),
                    "frequency_penalty": api_params.get(
                        "frequency_penalty", 0.0
                    ),
                    "presence_penalty": api_params.get(
                        "presence_penalty", 0.0
                    ),
                    "num_predict": self.output_max_length or 1024,
                },
            }
            response = requests.post(
                f"{self.api_base_url}/ollama/api/chat",
                headers=self.headers,
                json=model_params,
                verify=settings.HACTAR_VERIFY_SSL,
            )
            response.raise_for_status()
            result = response.json()
            self.logs["model_params"] = model_params
            return cast(str, result.get("message", {}).get("content", ""))

        model_params = {
            "model": self.model_name,
            "prompt": input_text,
            "max_tokens": self.output_max_length,
            "temperature": self.temperature,
            **api_params,
        }
        response = requests.post(
            f"{self.api_base_url}/ollama/api/chat",
            headers=self.headers,
            json=model_params,
            verify=settings.HACTAR_VERIFY_SSL,
        )
        response.raise_for_status()
        result = response.json()
        self.logs["model_params"] = model_params
        return cast(str, result.get("message", {}).get("content", ""))
