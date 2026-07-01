"""
chatbot_routes.py
- POST /ask              — answer using Pinecone context + Ollama (disk fallback)
- GET  /history/{pid}   — saved Q&A history
- GET  /debug/{pid}     — debug: check what vectors exist for a project
- GET  /health          — check if Ollama is reachable and which models are pulled
"""
import os
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import httpx

from ..database import get_db
from ..auth import verify_token
from ..permissions import verify_user_role
from ..services.pinecone_service import search_vectors, _get_index
from ..models import ChatbotMessage, ProjectFile

router = APIRouter()

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
)
OLLAMA_GEN_URL   = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_TAGS_URL  = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_MODEL     = "qwen2.5-coder"
OLLAMA_TIMEOUT   = 180.0   
MAX_CONTEXT_CHARS = 3000   

class HistoryMessage(BaseModel):
    role:    str
    content: str

class ChatbotRequest(BaseModel):
    project_id: int
    file_id:    int
    question:   str
    history:    Optional[list[HistoryMessage]] = []

def _read_file_from_disk(file_obj) -> str:
    candidates = [
        file_obj.file_path,
        os.path.join("backend", file_obj.file_path),
        os.path.join("uploads", f"project_{file_obj.project_id}", file_obj.filename),
        os.path.join("backend", "uploads", f"project_{file_obj.project_id}", file_obj.filename),
    ]
    if file_obj.file_path and file_obj.file_path.startswith(("backend/", "backend\\")):
        candidates.append(file_obj.file_path[8:])
    for path in candidates:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    return fh.read()
            except Exception:
                continue
    return ""

async def _check_ollama_ready() -> tuple[bool, str]:
    """Returns (is_ready, message). Checks Ollama is up AND model is pulled."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(OLLAMA_TAGS_URL)
            resp.raise_for_status()
            data   = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_found = any(OLLAMA_MODEL in m for m in models)
            if not model_found:
                return False, (
                    f"Model '{OLLAMA_MODEL}' is not pulled. Run: "
                    f"ollama pull {OLLAMA_MODEL}  (available models: {', '.join(models) or 'none'})"
                )
            return True, "ready"
    except httpx.ConnectError:
        return False, "Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        return False, f"Could not reach Ollama: {e}"

@router.get("/health")
async def chatbot_health():
    """Quick check: is Ollama up, and is the model pulled?"""
    ok, msg = await _check_ollama_ready()
    return {"ollama_ready": ok, "message": msg, "model": OLLAMA_MODEL}

@router.get("/history/{project_id}")
def get_chatbot_history(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    verify_user_role(project_id, "READ", current_user, db)
    msgs = db.query(ChatbotMessage).filter(
        ChatbotMessage.project_id == project_id,
        ChatbotMessage.user_id    == current_user["user_id"]
    ).order_by(ChatbotMessage.created_at.asc()).all()
    return [{"id": m.id, "question": m.question, "answer": m.answer,
             "created_at": m.created_at.isoformat()} for m in msgs]

@router.get("/debug/{project_id}")
async def debug_vectors(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    verify_user_role(project_id, "READ", current_user, db)
    idx = _get_index()
    if not idx:
        return {"error": "Pinecone not initialized", "pinecone_ok": False}

    ns   = f"project_{project_id}"
    info = {"namespace": ns, "pinecone_ok": True}
    try:
        stats    = idx.describe_index_stats()
        ns_stats = stats.get("namespaces", {})
        info["namespace_exists"] = ns in ns_stats
        info["vector_count"]     = ns_stats.get(ns, {}).get("vector_count", 0)
        info["all_namespaces"]   = list(ns_stats.keys())
    except Exception as e:
        info["stats_error"] = str(e)

    files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    info["db_files"] = [{"id": f.id, "name": f.filename, "path": f.file_path} for f in files]

    ollama_ok, ollama_msg = await _check_ollama_ready()
    info["ollama_ready"]  = ollama_ok
    info["ollama_message"] = ollama_msg
    return info

@router.post("/ask")
async def ask_chatbot(
    req: ChatbotRequest,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    verify_user_role(req.project_id, "READ", current_user, db)

    file_obj = db.query(ProjectFile).filter(ProjectFile.id == req.file_id).first()
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")
    filename = file_obj.filename

    ollama_ok, ollama_msg = await _check_ollama_ready()
    if not ollama_ok:
        answer = f" {ollama_msg}"
        try:
            db.add(ChatbotMessage(project_id=req.project_id, user_id=current_user["user_id"],
                                   question=req.question, answer=answer))
            db.commit()
        except Exception:
            db.rollback()
        return {"answer": answer, "sources": [filename], "context_source": "none"}

    context_block, context_source, chunks = "", "none", []
    try:
        chunks = search_vectors(req.project_id, [req.file_id], req.question, top_k=4)
    except Exception as e:
        print(f"[chatbot] Pinecone error: {e}")

    if chunks:
        parts = [c.get("chunk_text", "").strip() for c in chunks if c.get("chunk_text", "").strip()]
        if parts:
            context_block  = "\n\n".join(parts)[:MAX_CONTEXT_CHARS]
            context_source = "pinecone"

    if not context_block:
        disk_content = _read_file_from_disk(file_obj)
        if disk_content.strip():
            context_block  = disk_content[:MAX_CONTEXT_CHARS]
            context_source = "disk"

    history_str = ""
    if req.history:
        turns = [f"{'User' if m.role=='user' else 'Assistant'}: {m.content.strip()}" for m in req.history[-2:]]
        history_str = "\n".join(turns) + "\n" if turns else ""

    if context_block:
        prompt = (
            f"File '{filename}':\n```\n{context_block}\n```\n"
            + (f"{history_str}\n" if history_str else "")
            + f"Q: {req.question}\nA:"
        )
    else:
        prompt = f"No content found for '{filename}'. Tell the user to re-upload it.\nQ: {req.question}\nA:"

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(OLLAMA_GEN_URL, json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                      "num_predict": 400,    
                      "temperature": 0.3,
                }
            })
            resp.raise_for_status()
            answer = resp.json().get("response", "").strip()
            if not answer:
                answer = "The AI returned an empty response. Please try again."
            elapsed = time.time() - start
            print(f"[chatbot] Ollama responded in {elapsed:.1f}s")
    except httpx.TimeoutException:
        elapsed = time.time() - start
        answer = (
            f"⏱️ Ollama timed out after {elapsed:.0f}s. This usually means:\n"
            f"1. Your machine is running the model on CPU (slow) — first response especially.\n"
            f"2. Try: `ollama run {OLLAMA_MODEL}` once in a terminal to pre-load the model, then retry here.\n"
            f"3. Consider a smaller model like `qwen2.5-coder:1.5b` if your hardware is limited."
        )
    except httpx.HTTPStatusError as e:
        answer = f" Ollama returned HTTP {e.response.status_code}. Check `ollama serve` logs."
    except Exception as e:
        answer = f" Unexpected error calling Ollama: {e}"

    try:
        db.add(ChatbotMessage(project_id=req.project_id, user_id=current_user["user_id"],
                               question=req.question, answer=answer))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[chatbot] DB save error: {e}")

    sources = list({c.get("file_name") for c in chunks if c.get("file_name")}) if chunks else [filename]
    return {"answer": answer, "sources": sources, "context_source": context_source}