import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ProjectFile, CodeReview, Activity, Project
from ..ai.ai_reviewer import generate_review, generate_file_review
from ..auth import verify_token
from ..permissions import verify_user_role
from ..websocket.socket_manager import sio

router = APIRouter()


def _safe_list(value):
    """Always return a list, never crash."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _safe_str(value):
    """Always return a valid string, filter out bad data."""
    if not value or value in ["None", "null", "undefined", "unknown"]:
        return ""
    if isinstance(value, str):
        if value.strip().lower() in ["none", "null", "undefined", "unknown"]:
            return ""
        return value
    return str(value)


def _safe_score(value):
    """Return int 0-100, default 0."""
    try:
        s = int(float(value))
        return max(0, min(100, s))
    except (TypeError, ValueError):
        return 0

from pydantic import BaseModel
from typing import Optional

class QuickReviewRequest(BaseModel):
    filename: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[str] = None
    changed_content: Optional[str] = None

@router.post("/file/{file_id}")
async def review_file(
    file_id: int,
    req: Optional[QuickReviewRequest] = None,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):

    file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(file.project_id, "READ", current_user, db)

    from .project_routes import MODIFIED_DIFFS
    diff_content = MODIFIED_DIFFS.get(file_id, "")

    content_to_use = req.changed_content if (req and req.changed_content is not None) else (req.content if req else None)

    if diff_content:
        code_to_review = diff_content
        MODIFIED_DIFFS[file_id] = ""
        filename = req.filename or file.filename if req else file.filename
        file_path = req.file_path or file.file_path if req else file.file_path
    elif req and content_to_use is not None:
        code_to_review = content_to_use
        filename = req.filename or file.filename
        file_path = req.file_path or file.file_path
    else:
        path = file.file_path
        if not os.path.exists(path):
            if os.path.exists(os.path.join("backend", path)):
                path = os.path.join("backend", path)
            elif (path.startswith("backend/") or path.startswith("backend\\")) and os.path.exists(path[8:]):
                path = path[8:]
            else:
                cand1 = os.path.join("backend", "uploads", f"project_{file.project_id}", file.filename)
                cand2 = os.path.join("uploads", f"project_{file.project_id}", file.filename)
                if os.path.exists(cand1):
                    path = cand1
                elif os.path.exists(cand2):
                    path = cand2

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Source file missing on disk")

        code_to_review = code
        filename = file.filename
        file_path = file.file_path

    ai_review = generate_file_review(filename, code_to_review)

    if ai_review.get("error") or ai_review.get("_source") == "error":
        raise HTTPException(status_code=503, detail="AI Review Service Unavailable")

    score              = _safe_score(ai_review.get("overall_score", 0))
    issues_text        = _safe_str(ai_review.get("code_issue", ""))
    suggestions_text   = _safe_str(ai_review.get("suggested_fix", ""))
    bad_practices_text = _safe_str(ai_review.get("explanation", ""))
    perf_text          = _safe_str(ai_review.get("optimization", ""))
    comments_text      = _safe_str(ai_review.get("generated_documentation_comments", ""))
    doc_blob           = json.dumps(ai_review)

    try:
        review = CodeReview(
            project_id               = file.project_id,
            file_id                  = file.id,
            issues                   = issues_text,
            suggestions              = suggestions_text,
            documentation            = doc_blob,
            bad_practices            = bad_practices_text,
            performance_improvements = perf_text,
            generated_comments       = comments_text,
            score                    = score,
            created_at               = datetime.utcnow(),
        )
        db.add(review)
        db.add(Activity(
            action     = f"Review generated for {filename}",
            project_id = file.project_id,
            user_id    = current_user["user_id"],
            timestamp  = datetime.utcnow(),
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[review/file] DB save error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save review")

    try:
        await sio.emit("notification", {
            "type":       "review_completed",
            "message":    f"Review completed for {filename}",
            "project_id": file.project_id,
            "timestamp":  datetime.utcnow().isoformat(),
        })
    except Exception:
        pass

    return {
        "review_id": review.id,
        "score":     score,
        "ai_review": ai_review,
        "file_name": filename,
        "file_path": file_path,
        "filename":  filename,
        "filepath":  file_path,
    }

@router.get("/history/{project_id}")
def review_history(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Never crashes — returns [] on any error."""
    verify_user_role(project_id, "READ", current_user, db)
    try:
        reviews = db.query(CodeReview).filter(
            CodeReview.project_id == project_id
        ).order_by(CodeReview.created_at.desc()).all()

        result = []
        for r in reviews:
            doc: dict = {}
            try:
                if r.documentation:
                    doc = json.loads(r.documentation)
            except Exception:
                pass

            try:
                file_obj = db.query(ProjectFile).filter(
                    ProjectFile.id == r.file_id).first()
                filename = file_obj.filename if file_obj else f"File #{r.file_id}"
                file_path = file_obj.file_path if file_obj else ""
            except Exception:
                filename = f"File #{r.file_id}"
                file_path = ""

            result.append({
                "id":                       r.id,
                "file_id":                  r.file_id,
                "filename":                 filename,
                "file_path":                file_path,
                "filepath":                 file_path,
                "score":                    _safe_score(r.score),
                "created_at":               r.created_at.isoformat() + "Z" if r.created_at else "",
                "summary":                  _safe_str(doc.get("explanation")),
                "issues":                   _safe_str(doc.get("code_issue")),
                "suggestions":              _safe_str(doc.get("suggested_fix")),
                "optimizations":            _safe_str(doc.get("optimization")),
                "complexity":               _safe_str(doc.get("complexity_analysis") or "unknown"),
                "source":                   _safe_str(doc.get("_source") or "ollama"),
            })

        return result

    except Exception as exc:
        print(f"[review/history/{project_id}] error: {exc}")
        return []

@router.get("/all")
def all_review_history(
    page:       int = Query(default=1,   ge=1),
    page_size:  int = Query(default=10,  ge=1, le=100),
    search:     str = Query(default=""),
    project_id: int = Query(default=None),
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        if project_id:
            verify_user_role(project_id, "READ", current_user, db)
            
        q = db.query(CodeReview)
        if project_id:
            q = q.filter(CodeReview.project_id == project_id)
        if search:
            q = q.filter(CodeReview.issues.ilike(f"%{search}%"))

        total   = q.count()
        reviews = q.order_by(CodeReview.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        result = []
        for r in reviews:
            doc: dict = {}
            try:
                if r.documentation:
                    doc = json.loads(r.documentation)
            except Exception:
                pass

            try:
                file_obj    = db.query(ProjectFile).filter(ProjectFile.id == r.file_id).first()
                project_obj = db.query(Project).filter(Project.id == r.project_id).first()
                filename     = file_obj.filename    if file_obj    else f"File #{r.file_id}"
                file_path    = file_obj.file_path   if file_obj    else ""
                project_name = project_obj.name     if project_obj else f"Project #{r.project_id}"
            except Exception:
                filename = f"File #{r.file_id}"
                file_path = ""
                project_name = f"Project #{r.project_id}"

            result.append({
                "id":           r.id,
                "file_id":      r.file_id,
                "filename":     filename,
                "file_path":    file_path,
                "project_id":   r.project_id,
                "project_name": project_name,
                "score":        _safe_score(r.score),
                "created_at":   r.created_at.isoformat() + "Z" if r.created_at else "",
                "summary":      _safe_str(doc.get("explanation")),
                "issues":       [_safe_str(doc.get("code_issue"))] if doc.get("code_issue") else [],
                "suggestions":  [_safe_str(doc.get("suggested_fix"))] if doc.get("suggested_fix") else [],
                "complexity":   _safe_str(doc.get("complexity_analysis") or "unknown"),
            })

        return {
            "total":     total,
            "page":      page,
            "page_size": page_size,
            "pages":     max(1, (total + page_size - 1) // page_size),
            "reviews":   result,
        }
    except Exception as exc:
        print(f"[review/all] error: {exc}")
        return {"total": 0, "page": 1, "page_size": page_size, "pages": 1, "reviews": []}

@router.get("/analytics/trends")
def review_trends(project_id: int = None, db: Session = Depends(get_db)):
    """Never throws 500. Returns safe empty structure if no data."""
    try:
        q = db.query(CodeReview)
        if project_id:
            q = q.filter(CodeReview.project_id == project_id)
        reviews      = q.all()
        trend: dict  = {}
        total_score  = 0.0
        scored_count = 0

        for r in reviews:
            if r.created_at:
                day = r.created_at.strftime("%Y-%m-%d")
                trend[day] = trend.get(day, 0) + 1
            try:
                s = float(r.score) if r.score is not None else None
                if s is not None:
                    total_score  += s
                    scored_count += 1
            except (TypeError, ValueError):
                pass

        avg_score = round(total_score / scored_count, 1) if scored_count else 0

        try:
            files_reviewed = db.query(CodeReview.file_id).distinct().count()
        except Exception:
            files_reviewed = 0

        return {
            "total_reviews":  len(reviews),
            "average_score":  avg_score,
            "trend":          dict(sorted(trend.items())),
            "top_issues":     {},
            "files_reviewed": files_reviewed,
        }
    except Exception as exc:
        print(f"[review/analytics/trends] error: {exc}")
        return {
            "total_reviews": 0,
            "average_score": 0,
            "trend":         {},
            "top_issues":    {},
            "files_reviewed": 0,
        }

@router.get("/auto/{project_id}")
async def auto_review_project(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    verify_user_role(project_id, "READ", current_user, db)
    
    file = db.query(ProjectFile).filter(ProjectFile.project_id == project_id, ProjectFile.needs_review == True).first()
    
    if not file:
        return {
            "type": "manual",
            "message": "No changed files. Manual review required"
        }
        
    try:
        with open(file.file_path, "r", encoding="utf-8", errors="ignore") as fh:
            code = fh.read()
    except FileNotFoundError:
        return {
            "type": "manual",
            "message": "Source file missing on disk. Manual review required"
        }

    ai_review = generate_file_review(file.filename, code)
    
    if ai_review.get("error") or ai_review.get("_source") == "error":
        raise HTTPException(status_code=503, detail="AI Review Service Unavailable")

    score              = _safe_score(ai_review.get("overall_score", 0))
    issues_text        = _safe_str(ai_review.get("code_issue", ""))
    suggestions_text   = _safe_str(ai_review.get("suggested_fix", ""))
    bad_practices_text = _safe_str(ai_review.get("explanation", ""))
    perf_text          = _safe_str(ai_review.get("optimization", ""))
    comments_text      = _safe_str(ai_review.get("generated_documentation_comments", ""))
    doc_blob           = json.dumps(ai_review)

    try:
        review = CodeReview(
            project_id               = file.project_id,
            file_id                  = file.id,
            issues                   = issues_text,
            suggestions              = suggestions_text,
            documentation            = doc_blob,
            bad_practices            = bad_practices_text,
            performance_improvements = perf_text,
            generated_comments       = comments_text,
            score                    = score,
            created_at               = datetime.utcnow(),
        )
        db.add(review)
        db.add(Activity(
            action     = f"Auto review generated for {file.filename}",
            project_id = file.project_id,
            user_id    = current_user["user_id"],
            timestamp  = datetime.utcnow(),
        ))
        
        file.needs_review = False
        
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[review/auto] DB save error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to save review")

    try:
        await sio.emit("notification", {
            "type":       "review_completed",
            "message":    f"Automatic review completed for {file.filename}",
            "project_id": file.project_id,
            "timestamp":  datetime.utcnow().isoformat(),
        })
    except Exception:
        pass

    return {
        "type": "automatic",
        "file": file.filename,
        "file_id": file.id,
        "review": {
            "review_id": review.id,
            "score":     score,
            "ai_review": ai_review,
            "file_name": file.filename,
            "file_path": file.file_path,
            "filename": file.filename,
            "filepath": file.file_path,
        }
    }
