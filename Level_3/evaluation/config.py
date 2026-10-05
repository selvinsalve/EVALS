"""
Configuration settings for the DeepEval Evaluation Wrapper.
Handles LLM judge configuration (Ollama or OpenAI), metric thresholds,
paths for golden datasets and evaluation reports.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.models import OllamaModel, OpenAIModel


class EvaluationSettings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    GOLDEN_DATASETS_DIR: Path = BASE_DIR / "golden_datasets"
    REPORTS_DIR: Path = BASE_DIR / "evaluation" / "reports"
    DOCUMENTS_DIR: Path = BASE_DIR / "data" / "documents"
    DB_PATH: Path = BASE_DIR / "data" / "orders.db"

    # Evaluation Model Settings
    EVAL_LLM_PROVIDER: str = os.getenv("EVAL_LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Application endpoints (for HTTP black-box adapter if used)
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    # Metric Thresholds
    ANSWER_RELEVANCY_THRESHOLD: float = 0.5
    FAITHFULNESS_THRESHOLD: float = 0.5
    CONTEXTUAL_PRECISION_THRESHOLD: float = 0.5
    CONTEXTUAL_RECALL_THRESHOLD: float = 0.5
    CONTEXTUAL_RELEVANCY_THRESHOLD: float = 0.5
    TOOL_USE_THRESHOLD: float = 0.5
    ROLE_ADHERENCE_THRESHOLD: float = 0.5
    KNOWLEDGE_RETENTION_THRESHOLD: float = 0.5
    CONVERSATION_COMPLETENESS_THRESHOLD: float = 0.5
    GOAL_ACCURACY_THRESHOLD: float = 0.5
    TOPIC_ADHERENCE_THRESHOLD: float = 0.5
    GEVAL_THRESHOLD: float = 0.5

    # Execution controls
    ASYNC_MODE: bool = False  # Set False for reliable sequential execution with local Ollama
    VERBOSE_MODE: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


_eval_settings: Optional[EvaluationSettings] = None


def get_eval_settings() -> EvaluationSettings:
    global _eval_settings
    if _eval_settings is None:
        _eval_settings = EvaluationSettings()
        _eval_settings.GOLDEN_DATASETS_DIR.mkdir(parents=True, exist_ok=True)
        _eval_settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return _eval_settings


def get_eval_model(settings: Optional[EvaluationSettings] = None) -> DeepEvalBaseLLM:
    """
    Returns the configured DeepEval LLM judge model.
    Defaults to OllamaModel with local Qwen 2.5, or OpenAIModel if configured.
    """
    s = settings or get_eval_settings()
    provider = s.EVAL_LLM_PROVIDER.lower().strip()

    if provider == "openai" and s.OPENAI_API_KEY:
        return OpenAIModel(
            model=s.OPENAI_MODEL,
            api_key=s.OPENAI_API_KEY,
        )

    # Default to OllamaModel
    return OllamaModel(
        model=s.OLLAMA_MODEL,
        base_url=s.OLLAMA_BASE_URL,
    )
