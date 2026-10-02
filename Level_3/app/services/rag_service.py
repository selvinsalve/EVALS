from typing import List, Tuple
from app.rag.retriever import PolicyRetriever
from app.schemas.assistant import SourceCitation
from app.utils.logging import logger


class RAGService:
    """High-level application service for RAG operations."""

    def __init__(self, retriever: PolicyRetriever = None):
        self.retriever = retriever or PolicyRetriever()

    def get_policy_context(self, query: str, top_k: int = 4) -> Tuple[str, List[SourceCitation]]:
        """Retrieve relevant policies and return context string and citation objects."""
        logger.info("Executing RAG retrieval for query: '%s'", query)
        context, citations = self.retriever.retrieve(query, top_k=top_k)
        logger.info("Retrieved %d citations from vector store.", len(citations))
        return context, citations
