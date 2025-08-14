"""Base LLM provider interface."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMProvider(ABC):
    """Abstract base class for LLM providers with built-in retry logic."""

    def __init__(self, api_key: str, model: str, max_retries: int = 3, base_delay: float = 1.0):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay

    @abstractmethod
    async def _make_api_call(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Make the actual API call to the LLM provider.

        Returns:
            {
                'response': str,
                'status': 'success' | 'error',
                'error_message': Optional[str],
                'metadata': Dict[str, Any]
            }
        """
        pass

    async def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response from LLM provider with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                return await self._make_api_call(prompt, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    logging.error(f"Final attempt failed for {self.model}: {e}")
                    return {
                        "response": None,
                        "status": "error",
                        "error_message": str(e),
                        "metadata": {"model": self.model, "attempts": attempt + 1},
                    }

                delay = self.base_delay * (2**attempt)
                logging.warning(
                    f"Attempt {attempt + 1} failed for {self.model}: {e}. Retrying in {delay}s"
                )
                await asyncio.sleep(delay)

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate API credentials."""
        pass
