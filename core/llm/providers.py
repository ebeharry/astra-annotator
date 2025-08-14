"""LLM provider implementations."""

import os
from typing import Any, Dict, Optional

import aiohttp

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4",
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
    ):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        super().__init__(api_key, model)
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make API call to OpenAI."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        # Only add temperature if it's not the default (some models like GPT-5 don't support custom temperature)
        temperature = kwargs.get("temperature", self.temperature)
        if temperature != 1.0:  # 1.0 is the default for OpenAI models
            data["temperature"] = temperature

        # Only add max_tokens if specified
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens is not None:
            data["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions", headers=headers, json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "response": result["choices"][0]["message"]["content"],
                        "status": "success",
                        "error_message": None,
                        "metadata": {"model": self.model, "usage": result.get("usage", {})},
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error {response.status}: {error_text}")

    def validate_credentials(self) -> bool:
        """Validate OpenAI API credentials."""
        try:
            return self.api_key.startswith("sk-") and len(self.api_key) > 20
        except (AttributeError, TypeError):
            return False


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-3-sonnet-20240229",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not provided")
        super().__init__(api_key, model)
        self.max_tokens = max_tokens or 4096  # Claude requires max_tokens
        self.temperature = temperature

    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make API call to Anthropic Claude."""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        data = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", self.temperature),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages", headers=headers, json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "response": result["content"][0]["text"],
                        "status": "success",
                        "error_message": None,
                        "metadata": {"model": self.model, "usage": result.get("usage", {})},
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"Claude API error {response.status}: {error_text}")

    def validate_credentials(self) -> bool:
        """Validate Anthropic API credentials."""
        try:
            return len(self.api_key) > 20 and self.api_key.startswith("sk-")
        except (AttributeError, TypeError):
            return False


class GrokProvider(LLMProvider):
    """xAI Grok provider."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "grok-beta",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ):
        api_key = api_key or os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("xAI API key not provided")
        super().__init__(api_key, model)
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make API call to xAI Grok."""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", self.temperature),
        }

        # Only add max_tokens if specified
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens is not None:
            data["max_tokens"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/chat/completions", headers=headers, json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "response": result["choices"][0]["message"]["content"],
                        "status": "success",
                        "error_message": None,
                        "metadata": {"model": self.model, "usage": result.get("usage", {})},
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"Grok API error {response.status}: {error_text}")

    def validate_credentials(self) -> bool:
        """Validate xAI API credentials."""
        try:
            return len(self.api_key) > 20
        except (AttributeError, TypeError):
            return False


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "gemini-pro",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ):
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not provided")
        super().__init__(api_key, model)
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make API call to Google Gemini."""
        headers = {"Content-Type": "application/json"}

        generation_config = {"temperature": kwargs.get("temperature", self.temperature)}

        # Only add maxOutputTokens if specified
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens

        data = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation_config}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "response": result["candidates"][0]["content"]["parts"][0]["text"],
                        "status": "success",
                        "error_message": None,
                        "metadata": {"model": self.model, "usage": result.get("usageMetadata", {})},
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error {response.status}: {error_text}")

    def validate_credentials(self) -> bool:
        """Validate Google API credentials."""
        try:
            return len(self.api_key) > 20
        except (AttributeError, TypeError):
            return False


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        api_key: str = None,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ):
        # Ollama doesn't need API key, but we keep interface consistent
        super().__init__(api_key or "local", model)
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make API call to Ollama."""
        headers = {"Content-Type": "application/json"}

        options = {"temperature": kwargs.get("temperature", self.temperature)}

        # Only add num_predict if specified
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        data = {"model": self.model, "prompt": prompt, "stream": False, "options": options}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate", headers=headers, json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "response": result["response"],
                        "status": "success",
                        "error_message": None,
                        "metadata": {
                            "model": self.model,
                            "eval_count": result.get("eval_count", 0),
                            "eval_duration": result.get("eval_duration", 0),
                        },
                    }
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")

    def validate_credentials(self) -> bool:
        """Validate Ollama connection."""
        try:
            # For Ollama, we check if the service is running
            return True  # Simplified validation
        except Exception:
            return False
