"""Base LLM client for OpenAI-compatible APIs."""

import time
import httpx
from openai import OpenAI
from typing import Optional
from loguru import logger


class BaseLLMClient:
    """OpenAI-compatible LLM client base class."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        **kwargs,
    ):
        """
        Initialize the LLM client.

        Args:
            api_base: API base URL (OpenAI-compatible endpoint)
            api_key: API key
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters
        """
        # Custom UA: some gateways (e.g. newapi.20200626.xyz) WAF-block
        # requests with the openai-python default "OpenAI/Python ..." UA.
        ua = "paper-pulse/1.0"
        self.client = OpenAI(
            base_url=api_base,
            api_key=api_key,
            http_client=httpx.Client(
                timeout=180, verify=False, headers={"User-Agent": ua},
            ),
            default_headers={"User-Agent": ua},
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs

        logger.debug(f"Initialized LLM client: {api_base} / {model}")

    def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with "role" and "content"
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional parameters

        Returns:
            The assistant's response text
        """
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            **kwargs,
        }

        try:
            response = self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            raise

    def chat_with_pdf(
        self,
        prompt: str,
        pdf_base64: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a chat completion request with a PDF file.

        Args:
            prompt: Text prompt
            pdf_base64: Base64 encoded PDF content
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            The assistant's response text
        """
        # Construct message with PDF as file attachment
        # Using the OpenAI vision API format which Gemini also supports
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:application/pdf;base64,{pdf_base64}",
                        },
                    },
                ],
            }
        ]

        # Stream to keep the connection alive: some gateways cap idle/TTFB
        # at ~60s, which large-PDF inference often exceeds.
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": True,
        }

        try:
            stream = self.client.chat.completions.create(**params)
            chunks: list[str] = []
            for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta.content
                if delta:
                    chunks.append(delta)
            return "".join(chunks)
        except Exception as e:
            logger.error(f"LLM chat with PDF error: {e}")
            raise


class ResilientLLMClient:
    """LLM client with retry and fallback across multiple providers."""

    # Keys that are not BaseLLMClient constructor parameters
    _non_client_keys = {"rate_limit"}

    def __init__(self, configs: list[dict], max_retries: int = 3, retry_delay: float = 1.0):
        self.configs = configs
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.clients: list[BaseLLMClient] = []
        for cfg in configs:
            clean = {k: v for k, v in cfg.items() if k not in self._non_client_keys}
            self.clients.append(BaseLLMClient(**clean))

    def chat(self, messages, temperature=None, max_tokens=None, **kwargs) -> str:
        return self._call_with_fallback(
            "chat", messages=messages,
            temperature=temperature, max_tokens=max_tokens, **kwargs,
        )

    def chat_with_pdf(self, prompt, pdf_base64, temperature=None, max_tokens=None) -> str:
        return self._call_with_fallback(
            "chat_with_pdf", prompt=prompt,
            pdf_base64=pdf_base64, temperature=temperature, max_tokens=max_tokens,
        )

    def _call_with_fallback(self, method_name: str, **kwargs) -> str:
        last_error = None
        for i, client in enumerate(self.clients):
            for attempt in range(1, self.max_retries + 1):
                try:
                    return getattr(client, method_name)(**kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"LLM provider {i+1}/{len(self.clients)} "
                        f"attempt {attempt}/{self.max_retries} failed: {e}"
                    )
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * attempt)
            logger.error(f"LLM provider {i+1} exhausted all retries, trying next...")
        raise last_error
