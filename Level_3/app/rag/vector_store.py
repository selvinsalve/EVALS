import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from app.config import get_settings
from app.utils.logging import logger

settings = get_settings()


class VectorStoreManager:
    """Manages ChromaDB client, collections, and vector search."""

    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None):
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME

        os.makedirs(self.persist_directory, exist_ok=True)

        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Select embedding function based on configuration
        self.embedding_function = self._get_embedding_function()

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"description": "E-commerce customer service policies and FAQs"},
        )

    def _get_embedding_function(self):
        """Returns appropriate embedding function (OpenAI if configured, else Chroma default ONNX)."""
        if settings.OPENAI_API_KEY and not settings.DEMO_MODE and settings.LLM_PROVIDER == "openai":
            try:
                logger.info("Using OpenAI embedding function: %s", settings.OPENAI_EMBEDDING_MODEL)
                return embedding_functions.OpenAIEmbeddingFunction(
                    api_key=settings.OPENAI_API_KEY,
                    model_name=settings.OPENAI_EMBEDDING_MODEL,
                )
            except Exception as e:
                logger.warning("Failed to initialize OpenAI embeddings, falling back to default: %s", e)

        # Chroma's built-in default embedding function (all-MiniLM-L6-v2 via ONNX)
        logger.info("Using ChromaDB default local embedding function.")
        return embedding_functions.DefaultEmbeddingFunction()

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        """Upsert documents into ChromaDB collection."""
        if not documents:
            return

        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info("Upserted %d documents into vector collection '%s'.", len(documents), self.collection_name)

    def query(self, query_text: str, n_results: int = 4) -> Dict[str, Any]:
        """Perform semantic similarity search against the collection."""
        count = self.collection.count()
        if count == 0:
            logger.warning("Vector store collection '%s' is empty.", self.collection_name)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        actual_n = min(n_results, count)
        results = self.collection.query(
            query_texts=[query_text],
            n_results=actual_n,
        )
        return results

    def count(self) -> int:
        """Return total document chunks indexed in the collection."""
        return self.collection.count()

    def clear(self) -> None:
        """Reset the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
        )
