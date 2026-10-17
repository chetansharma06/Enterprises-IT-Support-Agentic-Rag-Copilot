import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.core.network import ExternalDnsError
from app.rag.workflow import ask
from app.rag.vectorstore import add_documents
from app.services.ingestion import load_file, chunk_documents, SUPPORTED
from app.services.audit import write_audit

router = APIRouter(prefix="/api")
settings = get_settings()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)


def _is_overloaded(exc: Exception) -> bool:
    """True when Gemini says it is busy / rate limited (temporary problem)."""
    text = str(exc).upper()
    return any(w in text for w in ("503", "UNAVAILABLE", "HIGH DEMAND", "429", "RESOURCE_EXHAUSTED"))


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        result = ask(payload.question)
        write_audit(payload.question, result["source_used"], result.get("trace", []))

        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "trace": result.get("trace", []),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
        }

    except Exception as exc:
        if isinstance(exc, ExternalDnsError):
            logger.exception("DNS resolution failed while handling a chat request")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if getattr(exc, "winerror", None) == 10013 or "WinError 10013" in str(exc):
            logger.exception("Outbound network access was blocked while handling a chat request")
            raise HTTPException(
                status_code=503,
                detail=(
                    "Outbound HTTPS is blocked for this Python process (WinError 10013). "
                    "Allow .venv\\Scripts\\python.exe through the firewall or configure the corporate proxy "
                    "for Google Gemini, Pinecone, and Tavily, then retry."
                ),
            ) from exc
        if _is_overloaded(exc):
            logger.exception("Gemini is overloaded even after retries and backup model")
            raise HTTPException(
                status_code=503,
                detail="The AI service is busy right now. Please try again in a minute.",
            ) from exc
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your question. Please try again.",
        ) from exc


@router.post("/ingest")
async def ingest(file: UploadFile = File(...), x_admin_key: str = Header(default="")):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Supported: {', '.join(sorted(SUPPORTED))}")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename).name
    dest.write_bytes(await file.read())
    docs = load_file(dest)
    chunks = chunk_documents(docs)
    ids = add_documents(chunks)
    return {"message": "Document indexed", "file": dest.name, "chunks": len(chunks), "ids_created": len(ids)}