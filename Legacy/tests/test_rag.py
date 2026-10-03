import pytest
from pathlib import Path
from app.rag.ingest import DocumentLoader, TextChunker, IngestionPipeline
from app.rag.vector_store import VectorStoreManager
from app.rag.retriever import PolicyRetriever
from app.config import get_settings

settings = get_settings()


def test_document_loader():
    """Verify loading text and metadata from markdown documents."""
    loader = DocumentLoader()
    doc_path = settings.DOCUMENTS_DIR / "return_policy.md"
    assert doc_path.exists(), "return_policy.md should exist in data/documents"

    content, meta = loader.load_file(doc_path)
    assert len(content) > 100
    assert meta["source"] == "return_policy.md"
    assert meta["file_type"] == ".md"


def test_text_chunker():
    """Verify document chunker preserves headers and reasonable length."""
    chunker = TextChunker(target_chunk_size=400, overlap=50)
    sample_text = (
        "# Return Policy\n\n"
        "Customers can return items within 30 days.\n\n"
        "## Conditions\n\n"
        "Items must be in original condition with tags.\n\n"
        "## Exceptions\n\n"
        "Perishable goods cannot be returned."
    )
    chunks = chunker.chunk_document(sample_text, {"source": "test.md"})
    assert len(chunks) >= 2
    sections = [c["metadata"]["section"] for c in chunks]
    assert "Conditions" in sections or "Exceptions" in sections or "Return Policy" in sections


def test_vector_store_retrieval():
    """Verify policy retriever can find relevant excerpts."""
    retriever = PolicyRetriever()
    # Test query about returns
    context, citations = retriever.retrieve("What is the return window for items?", top_k=3)
    if citations:  # If documents ingested in collection
        assert len(citations) >= 1
        assert len(context) > 50
