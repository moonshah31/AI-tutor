import asyncio
import logging
from typing import List

from app.config import Settings
from app.providers.base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Adapter around the official Google GenAI SDK with server error fallbacks."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.gemini_api_key
        
        # Deduplicate models while keeping the primary model from Settings at the top
        primary_model = settings.gemini_model
        fallback_candidates = [
            primary_model,
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
        ]
        self._models: List[str] = list(dict.fromkeys(fallback_candidates))

    async def generate_response(self, prompt: str) -> str:
        if not self._api_key:
            logger.error("Gemini is not configured")
            raise AIProviderError("Tutor provider is not configured")

        try:
            from google import genai
            from google.genai.errors import ServerError

            client = genai.Client(api_key=self._api_key)
            last_error: Exception | None = None

            for model_name in self._models:
                # Attempt up to 2 retries for transient 503/500 spikes on each model
                for attempt in range(1, 3):
                    try:
                        result = await asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            contents=prompt,
                        )

                        text = getattr(result, "text", None)

                        if not isinstance(text, str) or not text.strip():
                            raise AIProviderError("Gemini returned an empty response")

                        return text.strip()

                    except ServerError as err:
                        last_error = err
                        logger.warning(
                            "Gemini model '%s' hit a server error (attempt %d/2): %s",
                            model_name,
                            attempt,
                            err,
                        )
                        if attempt < 2:
                            await asyncio.sleep(1.5 * attempt)

            # If all models in the fallback chain hit server errors
            raise AIProviderError(
                "Tutor provider is temporarily unavailable due to high server demand."
            ) from last_error

        except AIProviderError:
            raise

        except Exception as error:
            logger.exception(
                "Gemini request failed: %s",
                type(error).__name__,
            )

            raise AIProviderError("Tutor provider is unavailable") from error