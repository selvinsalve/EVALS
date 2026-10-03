import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.rag.vector_store import VectorStoreManager
from app.config import get_settings
from app.utils.logging import logger

settings = get_settings()


class DocumentLoader:
    """Loads text from markdown, text, and PDF files."""

    @staticmethod
    def load_file(file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """Load text content and base metadata from a given file."""
        ext = file_path.suffix.lower()
        base_meta = {
            "source": str(file_path.name),
            "file_type": ext,
            "file_path": str(file_path),
        }

        if ext in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content, base_meta

        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(file_path))
                text_pages = []
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_pages.append(page_text)
                return "\n\n".join(text_pages), base_meta
            except Exception as e:
                logger.error("Failed to parse PDF %s: %s", file_path, e)
                return "", base_meta

        else:
            logger.warning("Unsupported file format: %s", ext)
            return "", base_meta


class TextChunker:
    """Splits markdown and text documents into structured chunks with metadata."""

    def __init__(self, target_chunk_size: int = 500, overlap: int = 80):
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap

    def chunk_document(self, text: str, base_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split text into chunks, honoring section boundaries if available."""
        if not text.strip():
            return []

        chunks = []
        doc_name = base_metadata.get("source", "unknown")

        # Split by markdown headers if present
        header_pattern = re.compile(r"^(#{1,4}\s+.+)$", re.MULTILINE)
        sections = header_pattern.split(text)

        current_header = "General Overview"
        chunk_idx = 0

        i = 0
        while i < len(sections):
            part = sections[i].strip()
            if not part:
                i += 1
                continue

            if part.startswith("#"):
                current_header = part.lstrip("#").strip()
                i += 1
                continue

            # Process section body
            body = part
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

            current_chunk = ""
            for p in paragraphs:
                if len(current_chunk) + len(p) + 2 <= self.target_chunk_size:
                    current_chunk = f"{current_chunk}\n\n{p}".strip() if current_chunk else p
                else:
                    if current_chunk:
                        chunk_id = f"{doc_name}_chunk_{chunk_idx:03d}"
                        chunks.append({
                            "id": chunk_id,
                            "text": f"[{doc_name} | {current_header}]\n{current_chunk}",
                            "metadata": {
                                "document": doc_name,
                                "section": current_header,
                                "chunk_id": chunk_id,
                                "source": base_metadata.get("source", ""),
                            },
                        })
                        chunk_idx += 1

                    # If paragraph itself is very long, sub-chunk it
                    if len(p) > self.target_chunk_size:
                        sub_start = 0
                        while sub_start < len(p):
                            sub_end = min(sub_start + self.target_chunk_size, len(p))
                            sub_text = p[sub_start:sub_end]
                            chunk_id = f"{doc_name}_chunk_{chunk_idx:03d}"
                            chunks.append({
                                "id": chunk_id,
                                "text": f"[{doc_name} | {current_header}]\n{sub_text}",
                                "metadata": {
                                    "document": doc_name,
                                    "section": current_header,
                                    "chunk_id": chunk_id,
                                    "source": base_metadata.get("source", ""),
                                },
                            })
                            chunk_idx += 1
                            sub_start += self.target_chunk_size - self.overlap
                        current_chunk = ""
                    else:
                        current_chunk = p

            if current_chunk:
                chunk_id = f"{doc_name}_chunk_{chunk_idx:03d}"
                chunks.append({
                    "id": chunk_id,
                    "text": f"[{doc_name} | {current_header}]\n{current_chunk}",
                    "metadata": {
                        "document": doc_name,
                        "section": current_header,
                        "chunk_id": chunk_id,
                        "source": base_metadata.get("source", ""),
                    },
                })
                chunk_idx += 1

            i += 1

        return chunks


class IngestionPipeline:
    """Orchestrates document loading, chunking, and upserting into ChromaDB."""

    def __init__(self, vector_store: VectorStoreManager = None):
        self.vector_store = vector_store or VectorStoreManager()
        self.loader = DocumentLoader()
        self.chunker = TextChunker()

    def ingest_directory(self, docs_dir: Path) -> int:
        """Scan directory and ingest all .md, .txt, and .pdf documents."""
        if not docs_dir.exists():
            logger.warning("Documents directory does not exist: %s", docs_dir)
            return 0

        supported_extensions = {".md", ".txt", ".pdf"}
        all_chunks = []

        files = [p for p in docs_dir.glob("**/*") if p.is_file() and p.suffix.lower() in supported_extensions]
        logger.info("Found %d supported document files in %s", len(files), docs_dir)

        for file_path in sorted(files):
            content, meta = self.loader.load_file(file_path)
            if not content:
                continue

            chunks = self.chunker.chunk_document(content, meta)
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("No document chunks produced during ingestion.")
            return 0

        # Prepare payload for ChromaDB
        documents = [c["text"] for c in all_chunks]
        metadatas = [c["metadata"] for c in all_chunks]
        ids = [c["id"] for c in all_chunks]

        self.vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
        logger.info("Successfully ingested %d chunks from %d files.", len(all_chunks), len(files))
        return len(all_chunks)


def run_ingestion() -> int:
    """Convenience function to run document ingestion from configured directory."""
    docs_dir = settings.DOCUMENTS_DIR
    pipeline = IngestionPipeline()
    return pipeline.ingest_directory(docs_dir)
