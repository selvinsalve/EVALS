#!/home/rushikesh/Selvin/Level_1/myenv/bin/python
import os
import time
import shutil
import tempfile
import urllib.request
import json
from pathlib import Path
from typing import List, Optional, Any, Dict

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from deepeval.synthesizer import Synthesizer
from deepeval.synthesizer.config import ContextConstructionConfig
from deepeval.models import OllamaModel, OllamaEmbeddingModel

app = FastAPI(
    title="DeepEval Synthetic Goldens API",
    description="Backend API to synthesize evaluation goldens from custom documents (.md, .db, .txt, .pdf, etc.) via DeepEval and local Ollama.",
    version="1.0.0",
)

# Enable CORS so your frontend UI can connect from any port/domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GoldenModel(BaseModel):
    id: Optional[str] = None
    input: str = Field(description="Synthesized query/question")
    expected_output: Optional[str] = Field(default=None, description="Ground truth answer derived from context")
    context: List[str] = Field(default_factory=list, description="Context chunks used to synthesize this golden")
    evolutions: Optional[List[str]] = Field(default=None, description="Applied evolution techniques (e.g. In-Breadth, Reasoning)")
    synthetic_input_quality: Optional[float] = Field(default=None, description="Quality score of generated question")
    context_quality: Optional[float] = Field(default=None, description="Quality score of context chunk")
    source_file: Optional[str] = Field(default=None, description="Source document filename")
    additional_metadata: Optional[Dict[str, Any]] = None


class GenerateGoldensResponse(BaseModel):
    status: str = Field(description="'success' or 'error'")
    total_generated: int = Field(description="Total count of goldens generated")
    requested_count: int = Field(description="Number of goldens requested by the client")
    execution_time_seconds: float = Field(description="Total processing time in seconds")
    first_5_goldens: List[GoldenModel] = Field(description="First 5 goldens formatted for direct UI display")
    files_processed: List[str] = Field(description="List of document filenames processed")


def serialize_golden(golden: Any) -> GoldenModel:
    """Helper to extract attributes from DeepEval Golden object into GoldenModel."""
    metadata = getattr(golden, "additional_metadata", {}) or {}

    raw_ctx = getattr(golden, "context", [])
    if isinstance(raw_ctx, list):
        contexts = [str(c) for c in raw_ctx]
    elif raw_ctx:
        contexts = [str(raw_ctx)]
    else:
        contexts = []

    evolutions = metadata.get("evolutions")
    if evolutions is not None and not isinstance(evolutions, list):
        evolutions = [str(evolutions)]

    input_quality = metadata.get("synthetic_input_quality")
    if input_quality is not None:
        try:
            input_quality = round(float(input_quality), 3)
        except (ValueError, TypeError):
            pass

    context_quality = metadata.get("context_quality")
    if context_quality is not None:
        try:
            context_quality = round(float(context_quality), 3)
        except (ValueError, TypeError):
            pass

    source = getattr(golden, "source_file", None)
    if source:
        source = Path(source).name

    return GoldenModel(
        id=str(getattr(golden, "id", "")),
        input=str(getattr(golden, "input", "")),
        expected_output=str(getattr(golden, "expected_output", "")) if getattr(golden, "expected_output", None) else None,
        context=contexts,
        evolutions=evolutions,
        synthetic_input_quality=input_quality,
        context_quality=context_quality,
        source_file=source,
        additional_metadata=metadata,
    )


def extract_sqlite_to_markdown(db_path: Path) -> str:
    """Extract schemas, tables, and records from SQLite .db into Markdown tables for synthesizer chunking."""
    import sqlite3
    parts = [f"# Database Overview: {db_path.name}\n"]
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]

        if not tables:
            parts.append("Database contains no user tables.\n")
            conn.close()
            return "\n".join(parts)

        parts.append(f"**Database contains {len(tables)} tables:** {', '.join(f'`{t}`' for t in tables)}\n")

        for table in tables:
            parts.append(f"## Table: `{table}`\n")
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            row = cursor.fetchone()
            if row and row[0]:
                parts.append(f"**Schema:**\n```sql\n{row[0]}\n```\n")

            cursor.execute(f"SELECT * FROM `{table}` LIMIT 100;")
            cols = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            if cols and rows:
                parts.append(f"**Data ({len(rows)} records):**\n")
                parts.append("| " + " | ".join(cols) + " |")
                parts.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for r in rows:
                    parts.append("| " + " | ".join(str(val).replace("\n", " ") for val in r) + " |")
                parts.append("\n")
        conn.close()
    except Exception as e:
        parts.append(f"Warning: Error extracting SQLite content: {str(e)}\n")

    return "\n".join(parts)


def prepare_document_for_synthesis(file_path: Path, temp_dir: Path) -> Path:
    """
    Adapts various document types (.md, .db, .sql, .pdf, .txt, .json, .csv)
    into formats directly ingestible by DeepEval's chunker.
    """
    ext = file_path.suffix.lower()

    # Native formats supported by DeepEval
    if ext in [".md", ".markdown", ".mdx", ".txt", ".pdf", ".docx"]:
        return file_path

    # SQLite Database (.db, .sqlite, .sqlite3)
    if ext in [".db", ".sqlite", ".sqlite3"]:
        converted_path = temp_dir / f"{file_path.stem}_database.md"
        content = extract_sqlite_to_markdown(file_path)
        converted_path.write_text(content, encoding="utf-8")
        return converted_path

    # SQL scripts (.sql)
    if ext == ".sql":
        converted_path = temp_dir / f"{file_path.stem}_sql.md"
        sql_text = file_path.read_text(encoding="utf-8", errors="ignore")
        converted_path.write_text(f"# SQL Script: {file_path.name}\n\n```sql\n{sql_text}\n```", encoding="utf-8")
        return converted_path

    # JSON files
    if ext == ".json":
        converted_path = temp_dir / f"{file_path.stem}_json.md"
        try:
            data = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
            formatted = json.dumps(data, indent=2)
            converted_path.write_text(f"# JSON Data: {file_path.name}\n\n```json\n{formatted}\n```", encoding="utf-8")
        except Exception:
            raw = file_path.read_text(encoding="utf-8", errors="ignore")
            converted_path.write_text(raw, encoding="utf-8")
        return converted_path

    # CSV files
    if ext == ".csv":
        converted_path = temp_dir / f"{file_path.stem}_csv.md"
        try:
            import csv
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
            if rows:
                lines = [f"# CSV Data: {file_path.name}\n"]
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                for r in rows[1:]:
                    lines.append("| " + " | ".join(r) + " |")
                converted_path.write_text("\n".join(lines), encoding="utf-8")
                return converted_path
        except Exception:
            pass

    # Fallback to .txt
    converted_path = temp_dir / f"{file_path.stem}.txt"
    try:
        raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
        converted_path.write_text(raw_text, encoding="utf-8")
        return converted_path
    except Exception:
        return file_path


def execute_synthesis(doc_paths: List[str], num_goldens: int) -> List[Any]:
    """Synchronous DeepEval synthesizer run invoked via threadpool."""
    llm = OllamaModel(
        model="qwen2.5:7b-instruct-q4_K_M",
        base_url="http://localhost:11434",
    )

    embedder = OllamaEmbeddingModel(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
    )

    config = ContextConstructionConfig(
        embedder=embedder,
        critic_model=llm,
    )

    synthesizer = Synthesizer(
        model=llm,
        async_mode=False,
    )

    goldens = synthesizer.generate_goldens_from_docs(
        document_paths=doc_paths,
        context_construction_config=config,
        max_goldens_per_context=num_goldens,
    )

    return goldens


@app.get("/")
async def root():
    """Root info endpoint."""
    return {
        "service": "DeepEval Synthetic Goldens API",
        "status": "online",
        "documentation": "/docs",
        "generate_endpoint": "/api/generate-goldens",
    }


@app.get("/api/health")
async def health_check():
    """Health check verifying local Ollama connectivity."""
    ollama_ok = False
    models = []
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            ollama_ok = True
            models = [m.get("name") for m in data.get("models", [])]
    except Exception as e:
        ollama_ok = False
        models = [f"Error connecting: {str(e)}"]

    return {
        "status": "online",
        "ollama_connected": ollama_ok,
        "available_models": models,
        "target_llm": "qwen2.5:7b-instruct-q4_K_M",
        "target_embedder": "nomic-embed-text",
    }


@app.post("/api/generate-goldens", response_model=GenerateGoldensResponse)
async def generate_goldens(
    num_goldens: int = Form(5, description="Number of goldens to generate (max_goldens_per_context)"),
    document_text: Optional[str] = Form(None, description="Direct text or markdown content. Leave empty if uploading files."),
    files: List[UploadFile] = File(default=[], description="Uploaded document files (.md, .db, .txt, .pdf, etc.)"),
):
    """
    Main endpoint for frontend UI to send document files or text and requested goldens count.
    - If files are uploaded, they will be used as the document source.
    - If no files are uploaded, document_text will be used as the document content.
    Returns total generated goldens and specifically includes the first 5 in 'first_5_goldens'.
    """
    if num_goldens < 1:
        raise HTTPException(status_code=400, detail="num_goldens must be at least 1")

    temp_dir = tempfile.mkdtemp(prefix="deepeval_upload_")
    doc_paths: List[str] = []
    processed_names: List[str] = []

    try:
        # 1. Handle uploaded files (.md, .db, .txt, .pdf, etc.)
        valid_uploads = [f for f in files if f.filename and f.size and f.size > 0]
        if valid_uploads:
            for upload in valid_uploads:
                dest = Path(temp_dir) / upload.filename
                content = await upload.read()
                dest.write_bytes(content)
                adapted = prepare_document_for_synthesis(dest, Path(temp_dir))
                doc_paths.append(str(adapted))
                processed_names.append(upload.filename)
        # 2. Only use document_text if no files were uploaded (avoids treating label/title as a document)
        elif document_text and document_text.strip():
            text_file = Path(temp_dir) / "document_input.md"
            text_file.write_text(document_text.strip(), encoding="utf-8")
            doc_paths.append(str(text_file))
            processed_names.append("document_input.md")

        if not doc_paths:
            raise HTTPException(
                status_code=400,
                detail="No documents provided. Please upload files or provide document_text."
            )

        start_time = time.time()
        raw_goldens = await run_in_threadpool(execute_synthesis, doc_paths, num_goldens)
        elapsed = round(time.time() - start_time, 2)

        serialized_all = [serialize_golden(g) for g in raw_goldens]
        first_5 = serialized_all[:5]

        return GenerateGoldensResponse(
            status="success",
            total_generated=len(serialized_all),
            requested_count=num_goldens,
            execution_time_seconds=elapsed,
            first_5_goldens=first_5,
            files_processed=processed_names,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def custom_openapi():
    """Forces 'format: binary' on file uploads so Swagger UI displays the file upload picker button."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for s_name, s in schema.get("components", {}).get("schemas", {}).items():
        for p_name, prop in s.get("properties", {}).items():
            if p_name in ["files", "file"]:
                if "items" in prop:
                    prop["items"]["format"] = "binary"
                    prop["items"].pop("contentMediaType", None)
                else:
                    prop["format"] = "binary"
                    prop.pop("contentMediaType", None)
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
