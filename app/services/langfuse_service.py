from langfuse import Langfuse
from langfuse.context import ObservationLevel
from typing import Optional, Dict, Any
import logging

from app.config import settings


logger = logging.getLogger(__name__)


class LangFuseService:
    """Service for AI observability using Langfuse."""

    def __init__(self):
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
            self.enabled = True
            logger.info("Langfuse initialized successfully")
        else:
            self.client = None
            self.enabled = False
            logger.warning("Langfuse credentials not provided, observability disabled")

    def create_trace(
        self,
        name: str,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Create a new trace for monitoring."""
        if not self.enabled:
            return None

        try:
            return self.client.trace(
                name=name,
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Error creating trace: {e}")
            return None

    def log_generation(
        self,
        trace,
        model: str,
        prompt: str,
        completion: str,
        latency_ms: float,
        metadata: Optional[Dict] = None
    ):
        """Log an LLM generation."""
        if not self.enabled or not trace:
            return

        try:
            trace.generation(
                model=model,
                input=prompt,
                output=completion,
                metadata=metadata or {},
                level=ObservationLevel.GENERATION,
                usage={
                    "input": len(prompt.split()),
                    "output": len(completion.split()),
                    "total": len(prompt.split()) + len(completion.split())
                }
            )
        except Exception as e:
            logger.error(f"Error logging generation: {e}")

    def log_span(
        self,
        trace,
        name: str,
        input_data: Any,
        output_data: Any,
        latency_ms: float,
        metadata: Optional[Dict] = None
    ):
        """Log a custom span/operation."""
        if not self.enabled or not trace:
            return

        try:
            trace.span(
                name=name,
                input=input_data,
                output=output_data,
                metadata=metadata or {},
                level=ObservationLevel.DEFAULT
            )
        except Exception as e:
            logger.error(f"Error logging span: {e}")

    def log_rag_retrieval(
        self,
        trace,
        query: str,
        retrieved_docs: list,
        latency_ms: float
    ):
        """Log RAG retrieval operation."""
        if not self.enabled or not trace:
            return

        try:
            trace.span(
                name="rag_retrieval",
                input={"query": query},
                output={"retrieved_count": len(retrieved_docs)},
                metadata={
                    "documents": [doc.get("title", "") for doc in retrieved_docs]
                },
                level=ObservationLevel.DEFAULT
            )
        except Exception as e:
            logger.error(f"Error logging RAG retrieval: {e}")

    def flush(self):
        """Flush any pending events to Langfuse."""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.error(f"Error flushing Langfuse: {e}")


# Singleton instance
langfuse_service = LangFuseService()
