from typing import Optional, Any
from pydantic import BaseModel, Field
from app.config import get_settings
from app.utils.logging import logger

settings = get_settings()


class EvaluationConfig(BaseModel):
    """Configuration for DeepEval RAG and Conversational metrics and judge models."""

    # Model Provider Settings
    llm_provider: str = Field(default_factory=lambda: settings.LLM_PROVIDER)
    ollama_model: str = Field(default_factory=lambda: settings.OLLAMA_MODEL)
    ollama_base_url: str = Field(default_factory=lambda: settings.OLLAMA_BASE_URL)
    openai_api_key: Optional[str] = Field(default_factory=lambda: settings.OPENAI_API_KEY)
    openai_model: str = Field(default_factory=lambda: settings.OPENAI_MODEL)

    # General Metric Settings
    async_mode: bool = Field(default=False, description="Set False for stable sequential execution with local Ollama")
    include_reason: bool = Field(default=True, description="Whether to include chain-of-thought justifications")
    strict_mode: bool = Field(default=False, description="Whether metric failures fail tests with strict zero scores")
    verbose_mode: bool = Field(default=False)

    # RAG Metric Thresholds (0.0 to 1.0)
    faithfulness_threshold: float = Field(default=0.7)
    answer_relevancy_threshold: float = Field(default=0.7)
    contextual_relevancy_threshold: float = Field(default=0.6)
    contextual_precision_threshold: float = Field(default=0.6)
    contextual_recall_threshold: float = Field(default=0.6)

    # Conversational Metric Thresholds (0.0 to 1.0)
    turn_relevancy_threshold: float = Field(default=0.7)
    turn_faithfulness_threshold: float = Field(default=0.7)
    conversation_completeness_threshold: float = Field(default=0.7)
    role_adherence_threshold: float = Field(default=0.7)
    conversational_geval_threshold: float = Field(default=0.7)
    knowledge_retention_threshold: float = Field(default=0.7)

    # Chatbot Domain Context
    chatbot_role: str = Field(
        default="Professional AI Customer Support Assistant for an e-commerce platform specializing in order tracking, cancellations, refunds, returns, and store policies."
    )


def get_eval_model(config: Optional[EvaluationConfig] = None) -> Any:
    """
    Instantiate and return the appropriate DeepEval evaluation judge model.
    Defaults to local Ollama (e.g. Qwen 2.5), or OpenAI if explicitly configured.
    """
    cfg = config or EvaluationConfig()

    # 1. Ollama Provider (or fallback when OpenAI key is not provided)
    if cfg.llm_provider.lower() == "ollama" or not cfg.openai_api_key:
        try:
            from deepeval.models import OllamaModel
            logger.info("Initializing DeepEval OllamaModel: %s @ %s", cfg.ollama_model, cfg.ollama_base_url)
            return OllamaModel(
                model=cfg.ollama_model,
                base_url=cfg.ollama_base_url,
            )
        except Exception as e:
            logger.error("Failed to initialize OllamaModel: %s", e)
            raise

    # 2. OpenAI Provider
    logger.info("Initializing DeepEval OpenAI model: %s", cfg.openai_model)
    return cfg.openai_model
