from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """A safe, provider-neutral failure exposed to the application layer."""


class AIProvider(ABC):
    name: str

    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        """Generate a tutor answer from a fully constructed prompt."""
