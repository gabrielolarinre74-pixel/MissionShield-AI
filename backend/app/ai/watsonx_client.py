"""
MissionShield AI — IBM watsonx.ai / Granite client.

Wraps ibm_watsonx_ai Credentials + ModelInference as a lazily-initialized
singleton.  All configuration comes from environment variables — no
credentials are hardcoded or logged.

The pattern mirrors test_watsonx.py (the proven connection proof at repo root):
  - Credentials(url=..., api_key=...)
  - ModelInference(model_id=..., credentials=..., project_id=...)
  - model.chat(messages=[...], params={...})
  - response["choices"][0]["message"]["content"]

AI failures are caught here and surfaced as AIServiceError so the rest of
the application can return a graceful degraded response without crashing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.exceptions import MissionShieldError

logger = logging.getLogger(__name__)


class AIServiceError(MissionShieldError):
    """Raised when the IBM watsonx.ai / Granite service is unavailable or returns an error."""

    def __init__(self, detail: str = "") -> None:
        self.detail = detail
        super().__init__(f"AI service error: {detail}")


class WatsonxClient:
    """
    Singleton wrapper around ibm_watsonx_ai ModelInference.

    Lazily initialised on first use.  Configuration is read from Settings.
    Credentials are NEVER logged, returned in responses, or sent to external
    services other than the IBM watsonx.ai endpoint.
    """

    def __init__(self) -> None:
        self._model: Any = None  # ibm_watsonx_ai.ModelInference

    def _get_model(self) -> Any:
        """Lazily initialize and return the ModelInference instance."""
        if self._model is not None:
            return self._model

        if not settings.WATSONX_APIKEY:
            raise AIServiceError(
                "WATSONX_APIKEY is not configured. IBM Granite is unavailable."
            )
        if not settings.WATSONX_URL:
            raise AIServiceError(
                "WATSONX_URL is not configured. IBM Granite is unavailable."
            )
        if not settings.WATSONX_PROJECT_ID:
            raise AIServiceError(
                "WATSONX_PROJECT_ID is not configured. IBM Granite is unavailable."
            )
        if not settings.WATSONX_MODEL_ID:
            raise AIServiceError(
                "WATSONX_MODEL_ID is not configured. IBM Granite is unavailable."
            )

        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference

            credentials = Credentials(
                url=settings.WATSONX_URL,
                api_key=settings.WATSONX_APIKEY,
            )
            model = ModelInference(
                model_id=settings.WATSONX_MODEL_ID,
                credentials=credentials,
                project_id=settings.WATSONX_PROJECT_ID,
            )
            self._model = model
            logger.info(
                "WatsonxClient: initialized ModelInference (model_id=%s, project=%s)",
                settings.WATSONX_MODEL_ID,
                settings.WATSONX_PROJECT_ID,
            )
            return self._model
        except ImportError as exc:
            raise AIServiceError(
                "ibm_watsonx_ai package is not installed."
            ) from exc
        except Exception as exc:
            # Sanitise — never let credentials appear in log messages.
            logger.error("WatsonxClient: initialization failed: %s", type(exc).__name__)
            raise AIServiceError(
                "Failed to initialize IBM watsonx.ai client. "
                "Check WATSONX_* environment variables."
            ) from exc

    def chat(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int = 512,
    ) -> str:
        """
        Send a chat request to IBM Granite and return the response text.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-style message list: [{"role": "system", "content": "..."},
                                         {"role": "user", "content": "..."}]
        max_new_tokens : int
            Maximum tokens in the generated response.

        Returns
        -------
        str
            The model's response text.

        Raises
        ------
        AIServiceError
            If the model is misconfigured, unavailable, or returns an error.
        """
        model = self._get_model()
        try:
            params = {"max_new_tokens": max_new_tokens}
            response = model.chat(messages=messages, params=params)
            content = response["choices"][0]["message"]["content"]
            return content
        except AIServiceError:
            raise
        except KeyError as exc:
            logger.error("WatsonxClient: unexpected response shape: %s", exc)
            raise AIServiceError(
                "Unexpected response format from IBM Granite."
            ) from exc
        except Exception as exc:
            logger.error(
                "WatsonxClient: chat call failed: %s",
                type(exc).__name__,
            )
            raise AIServiceError(
                f"IBM Granite request failed: {type(exc).__name__}"
            ) from exc


# Module-level singleton — shared via get_watsonx_client() dependency.
_client: WatsonxClient | None = None


def get_watsonx_client() -> WatsonxClient:
    """FastAPI dependency / factory for the WatsonxClient singleton."""
    global _client
    if _client is None:
        _client = WatsonxClient()
    return _client
