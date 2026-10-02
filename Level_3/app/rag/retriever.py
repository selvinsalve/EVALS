from typing import List, Tuple
from app.rag.vector_store import VectorStoreManager
from app.schemas.assistant import SourceCitation
from app.utils.logging import logger


class PolicyRetriever:
    """Retrieves relevant policy and FAQ excerpts from vector store."""

    def __init__(self, vector_store: VectorStoreManager = None):
        self.vector_store = vector_store or VectorStoreManager()

    def retrieve(self, query: str, top_k: int = 4) -> Tuple[str, List[SourceCitation]]:
        """
        Query vector store and return concatenated context string along with structured citations.
        """
        if not query.strip():
            return "", []

        try:
            results = self.vector_store.query(query_text=query, n_results=top_k)
        except Exception as e:
            logger.error("Vector search query failed: %s", e)
            return "", []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if results.get("distances") else []

        if not documents:
            return "", []

        citations: List[SourceCitation] = []
        context_parts: List[str] = []

        seen_sources = set()

        for idx, (doc_text, meta) in enumerate(zip(documents, metadatas)):
            doc_name = meta.get("document", "policy.md")
            section_name = meta.get("section", "General")
            dist = distances[idx] if idx < len(distances) else None

            # Calculate relevance score approximation (1 / (1 + distance))
            rel_score = round(1.0 / (1.0 + dist), 3) if dist is not None else None

            # Semantic relevance guardrail: drop irrelevant chunks
            if rel_score is not None and rel_score < 0.42:
                continue

            citation_key = f"{doc_name}:{section_name}"
            if citation_key not in seen_sources:
                seen_sources.add(citation_key)
                citations.append(
                    SourceCitation(
                        document=doc_name,
                        section=section_name,
                        excerpt=doc_text[:280] + ("..." if len(doc_text) > 280 else ""),
                        score=rel_score,
                    )
                )

            context_parts.append(f"--- Document: {doc_name} (Section: {section_name}) ---\n{doc_text}")

        if not citations:
            return "", []

        combined_context = "\n\n".join(context_parts)
        return combined_context, citations
