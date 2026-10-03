import logging
import sys
from typing import Any, Dict, Optional
from app.config import get_settings


def setup_logger(name: str = "ai_order_assistant") -> logging.Logger:
    """Configure and return a structured logger instance."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()


def log_assistant_event(
    event_type: str,
    intent: Optional[str] = None,
    order_id: Optional[str] = None,
    used_order_api: bool = False,
    used_rag: bool = False,
    latency_ms: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log structured events for assistant requests with observability data."""
    payload = {
        "event": event_type,
        "intent": intent,
        "order_id": order_id,
        "used_order_api": used_order_api,
        "used_rag": used_rag,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
    }
    if extra:
        payload.update(extra)
    logger.info("ASSISTANT_EVENT %s", payload)
