from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database.seed import init_db, seed_data
from app.rag.ingest import run_ingestion
from app.rag.vector_store import VectorStoreManager
from app.api.health import router as health_router
from app.api.orders import router as orders_router
from app.api.assistant import router as assistant_router
from app.utils.logging import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycles."""
    logger.info("Initializing application resources...")
    # Initialize DB tables
    init_db()
    # Seed DB data if needed
    seed_data()

    # Verify vector store and auto-ingest documents if collection is empty
    try:
        vs = VectorStoreManager()
        if vs.count() == 0:
            logger.info("Vector store is empty. Ingesting policy documents...")
            count = run_ingestion()
            logger.info("Auto-ingested %d document chunks on startup.", count)
        else:
            logger.info("Vector store has %d indexed document chunks.", vs.count())
    except Exception as e:
        logger.warning("Could not auto-ingest documents on startup: %s", e)

    logger.info("Application startup completed successfully.")
    yield
    logger.info("Shutting down application resources.")


app = FastAPI(
    title="AI Order Assistant API",
    description="Production-grade AI Order & Customer Support Assistant with Live Order Data and RAG Knowledge Base.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for user-friendly errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception for %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact customer support."},
    )


# Include API Routers
app.include_router(health_router)
app.include_router(orders_router)
app.include_router(assistant_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
