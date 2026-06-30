from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import (
    ProjectFile, FileVersion, CommitHistory,
    RollbackHistory, Activity
)
from ..schemas import CommitCreate
from ..auth import verify_token
from ..permissions import verify_user_role

import os
import shutil
import difflib

router = APIRouter()


@router.post("/commit")
def create_commit(
    commit: CommitCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    file = db.query(ProjectFile).filter(
        ProjectFile.id == commit.file_id
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(file.project_id, "WRITE", current_user, db)

    latest = db.query(FileVersion).filter(
        FileVersion.file_id == file.id
    ).order_by(FileVersion.version_number.desc()).first()
    version_number = (latest.version_number + 1) if latest else 1

    version_folder = f"versions/project_{file.project_id}"
    os.makedirs(version_folder, exist_ok=True)
    snapshot_path = f"{version_folder}/{file.filename}_v{version_number}"
    shutil.copy(file.file_path, snapshot_path)

    version = FileVersion(
        file_id        = file.id,
        project_id     = file.project_id,
        version_number = version_number,
        commit_message = commit.commit_message,
        snapshot_path  = snapshot_path,
        created_by     = current_user["user_id"],
        author         = current_user.get("username", ""),
        created_at     = datetime.utcnow()
    )
    db.add(version)

    history = CommitHistory(
        project_id     = file.project_id,
        user_id        = current_user["user_id"],
        author         = current_user.get("username", ""),
        commit_message = commit.commit_message,
        created_at     = datetime.utcnow()
    )
    db.add(history)

    db.add(Activity(
        action     = f"Committed: {commit.commit_message}",
        project_id = file.project_id,
        user_id    = current_user["user_id"],
        timestamp  = datetime.utcnow()
    ))

    db.commit()

    return {
        "message": "Commit Created",
        "version": version_number,
        "version_id": version.id
    }

@router.get("/history/{project_id}")
def commit_history(
    project_id: int,
    db: Session = Depends(get_db)
):
    commits = db.query(CommitHistory).filter(
        CommitHistory.project_id == project_id
    ).order_by(CommitHistory.created_at.desc()).all()

    return [
        {
            "id":             c.id,
            "project_id":     c.project_id,
            "user_id":        c.user_id,
            "author":         c.author or f"User #{c.user_id}",
            "commit_message": c.commit_message,
            "created_at":     c.created_at.isoformat() if c.created_at else ""
        }
        for c in commits
    ]

@router.get("/versions/{file_id}")
def file_versions(
    file_id: int,
    db: Session = Depends(get_db)
):
    versions = db.query(FileVersion).filter(
        FileVersion.file_id == file_id
    ).order_by(FileVersion.version_number.asc()).all()

    return [
        {
            "id":             v.id,
            "file_id":        v.file_id,
            "project_id":     v.project_id,
            "version_number": v.version_number,
            "commit_message": v.commit_message,
            "author":         v.author or f"User #{v.created_by}",
            "created_at":     v.created_at.isoformat() if v.created_at else ""
        }
        for v in versions
    ]


@router.get("/compare/{version1}/{version2}")
def compare_versions(
    version1: int,
    version2: int,
    db: Session = Depends(get_db)
):
    v1 = db.query(FileVersion).filter(FileVersion.id == version1).first()
    v2 = db.query(FileVersion).filter(FileVersion.id == version2).first()

    if not v1 or not v2:
        return {"error": "One or both versions not found"}

    try:
        with open(v1.snapshot_path, "r", encoding="utf-8", errors="ignore") as f:
            lines1 = f.readlines()
    except FileNotFoundError:
        return {"error": f"Snapshot for version {v1.version_number} not found on disk"}

    try:
        with open(v2.snapshot_path, "r", encoding="utf-8", errors="ignore") as f:
            lines2 = f.readlines()
    except FileNotFoundError:
        return {"error": f"Snapshot for version {v2.version_number} not found on disk"}

    diff = list(difflib.unified_diff(
        lines1, lines2,
        fromfile=f"v{v1.version_number}",
        tofile=f"v{v2.version_number}",
        lineterm=""
    ))

    added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    return {
        "from_version": v1.version_number,
        "to_version":   v2.version_number,
        "added":        added,
        "removed":      removed,
        "diff":         diff
    }

@router.post("/rollback/{version_id}")
def rollback_version(
    version_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    version = db.query(FileVersion).filter(FileVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    file = db.query(ProjectFile).filter(ProjectFile.id == version.file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="Original file not found")

    verify_user_role(file.project_id, "ADMIN", current_user, db)

    if not os.path.exists(version.snapshot_path):
        raise HTTPException(status_code=404, detail="Snapshot file missing on disk")

    shutil.copy(version.snapshot_path, file.file_path)

    rollback = RollbackHistory(
        file_id        = file.id,
        project_id     = file.project_id,
        version_id     = version.id,
        version_number = version.version_number,
        rolled_back_by = current_user["user_id"],
        rolled_back_at = datetime.utcnow()
    )
    db.add(rollback)

    db.add(Activity(
        action     = f"Rolled back {file.filename} to v{version.version_number}",
        project_id = file.project_id,
        user_id    = current_user["user_id"],
        timestamp  = datetime.utcnow()
    ))

    db.commit()

    return {
        "message":          "Rollback Successful",
        "restored_version": version.version_number,
        "file":             file.filename
    }

@router.get("/rollback-history/{project_id}")
def rollback_history(
    project_id: int,
    db: Session = Depends(get_db)
):
    records = db.query(RollbackHistory).filter(
        RollbackHistory.project_id == project_id
    ).order_by(RollbackHistory.rolled_back_at.desc()).all()

    return [
        {
            "id":             r.id,
            "file_id":        r.file_id,
            "version_number": r.version_number,
            "rolled_back_by": r.rolled_back_by,
            "rolled_back_at": r.rolled_back_at.isoformat() if r.rolled_back_at else ""
        }
        for r in records
    ]
