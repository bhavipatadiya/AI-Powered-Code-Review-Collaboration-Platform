import os
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db
from ..models import (
    User, Project, ProjectFile, CodeReview,
    ChatMessage, Activity, CommitHistory,
    LoginHistory, AdminLog, Notification,
    FileVersion, RollbackHistory, RepoFolder
)
from ..auth import admin_only
from ..websocket.socket_manager import sio

router = APIRouter()


def _log(db, admin_id, action, target_id=None, detail=""):
    db.add(AdminLog(
        admin_id   = admin_id,
        action     = action,
        target_id  = target_id,
        detail     = detail,
        created_at = datetime.utcnow()
    ))
    db.commit()

@router.get("/overview")
def admin_overview(admin=Depends(admin_only), db: Session = Depends(get_db)):
    try:
        return {
            "users_count":      db.query(User).count() or 0,
            "projects_count":   db.query(Project).count() or 0,
            "files_count":      db.query(ProjectFile).count() or 0,
            "reviews_count":    db.query(CodeReview).count() or 0,
            "chats_count":      db.query(ChatMessage).count() or 0,
            "activities_count": db.query(Activity).count() or 0,
        }
    except Exception:
        return {
            "users_count": 0,
            "projects_count": 0,
            "files_count": 0,
            "reviews_count": 0,
            "chats_count": 0,
            "activities_count": 0
        }

@router.get("/users")
def all_users(admin=Depends(admin_only), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [
        {
            "display_id": idx + 1,        
            "id":         u.id,         
            "username":   u.username,
            "email":      u.email,
            "role":       u.role,
            "is_active":  u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for idx, u in enumerate(users)
    ]

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin=Depends(admin_only),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Cannot delete the admin account")

    username = user.username

    projects = db.query(Project).filter(Project.owner_id == user_id).all()
    project_ids = [p.id for p in projects]

    from ..models import ProjectCollaborator, ChatMessage
    collabs = db.query(ProjectCollaborator).filter(ProjectCollaborator.user_id == user_id).all()
    collab_project_ids = [c.project_id for c in collabs if c.project_id not in project_ids]
    
    for c_pid in collab_project_ids:
        sys_msg = ChatMessage(
            project_id=c_pid,
            sender_id=0,
            username="System",
            message=f"User {username} removed by admin",
            created_at=datetime.utcnow()
        )
        db.add(sys_msg)
        db.commit()
        db.refresh(sys_msg)
        try:
            sio.emit("chat_message", {
                "id": sys_msg.id,
                "project_id": sys_msg.project_id,
                "sender_id": sys_msg.sender_id,
                "username": sys_msg.username,
                "message": sys_msg.message,
                "timestamp": sys_msg.created_at.isoformat()
            }, room=f"project_{c_pid}")
        except Exception:
            pass

    try:
        await sio.emit("force_logout", {"message": "Your account has been removed by an administrator."}, room=f"user_{user_id}")
    except Exception:
        pass

    for pid in project_ids:

        files = db.query(ProjectFile).filter(ProjectFile.project_id == pid).all()
        for f in files:
            if f.file_path and os.path.exists(f.file_path):
                try:
                    os.remove(f.file_path)
                except Exception:
                    pass

        folder_path = f"uploads/project_{pid}"
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)

        version_folder = f"versions/project_{pid}"
        if os.path.exists(version_folder):
            shutil.rmtree(version_folder, ignore_errors=True)

        db.query(FileVersion).filter(FileVersion.project_id == pid).delete()
        db.query(RollbackHistory).filter(RollbackHistory.project_id == pid).delete()
        db.query(CommitHistory).filter(CommitHistory.project_id == pid).delete()
        db.query(CodeReview).filter(CodeReview.project_id == pid).delete()
        db.query(ChatMessage).filter(ChatMessage.project_id == pid).delete()
        db.query(Activity).filter(Activity.project_id == pid).delete()
        db.query(RepoFolder).filter(RepoFolder.project_id == pid).delete()
        db.query(ProjectFile).filter(ProjectFile.project_id == pid).delete()

    db.query(Project).filter(Project.owner_id == user_id).delete()

    db.query(Notification).filter(Notification.user_id == user_id).delete()
    db.query(LoginHistory).filter(LoginHistory.user_id == user_id).delete()
    db.query(Activity).filter(Activity.user_id == user_id).delete()

    db.delete(user)

    _log(db, admin["user_id"], "delete_user", user_id,
         f"Deleted user {username} and all associated data")

    return {"message": f"User {username} permanently deleted"}

@router.get("/projects")
def all_projects(admin=Depends(admin_only), db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [
        {
            "id":          p.id,
            "name":        p.name,
            "description": p.description,
            "owner_id":    p.owner_id,
            "created_at":  p.created_at.isoformat() if p.created_at else "",
        }
        for p in projects
    ]

@router.get("/files")
def all_files(admin=Depends(admin_only), db: Session = Depends(get_db)):
    files = db.query(ProjectFile).all()
    return [
        {
            "id":          f.id,
            "filename":    f.filename,
            "file_type":   f.file_type,
            "project_id":  f.project_id,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else "",
        }
        for f in files
    ]

@router.get("/reviews")
def all_reviews(admin=Depends(admin_only), db: Session = Depends(get_db)):
    reviews = db.query(CodeReview).order_by(CodeReview.created_at.desc()).all()
    return [
        {
            "id":         r.id,
            "project_id": r.project_id,
            "file_id":    r.file_id,
            "score":      r.score or 0,
            "issues":     (r.issues or "")[:200],
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in reviews
    ]

@router.get("/chats")
def all_chats(admin=Depends(admin_only), db: Session = Depends(get_db)):
    chats = db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(200).all()
    return [
        {
            "id":         c.id,
            "project_id": c.project_id,
            "sender_id":  c.sender_id,
            "username":   c.username,
            "message":    c.message,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in chats
    ]

@router.get("/activity")
def all_activity(admin=Depends(admin_only), db: Session = Depends(get_db)):
    activities = db.query(Activity).order_by(Activity.timestamp.desc()).limit(200).all()
    return [
        {
            "id":         a.id,
            "action":     a.action,
            "project_id": a.project_id,
            "user_id":    a.user_id,
            "timestamp":  a.timestamp.isoformat() if a.timestamp else "",
        }
        for a in activities
    ]

@router.get("/login-history")
def login_history(admin=Depends(admin_only), db: Session = Depends(get_db)):
    logs = db.query(LoginHistory).order_by(LoginHistory.created_at.desc()).limit(200).all()
    return [
        {
            "id":         l.id,
            "user_id":    l.user_id,
            "ip_address": l.ip_address,
            "user_agent": (l.user_agent or "")[:80],
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in logs
    ]

@router.get("/logs")
def admin_logs(admin=Depends(admin_only), db: Session = Depends(get_db)):
    logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(100).all()
    return [
        {
            "id":         l.id,
            "admin_id":   l.admin_id,
            "action":     l.action,
            "target_id":  l.target_id,
            "detail":     l.detail,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in logs
    ]

@router.delete("/projects/{project_id}")
async def delete_project_admin(project_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    for f in files:
        if f.file_path and os.path.exists(f.file_path):
            try:
                os.remove(f.file_path)
            except:
                pass
                
    folder_path = f"uploads/project_{project_id}"
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)
        
    db.query(Project).filter(Project.id == project_id).delete()
    _log(db, admin["user_id"], "delete_project", project_id, f"Deleted project {project.name}")
    db.commit()
    return {"message": "Project deleted"}

@router.delete("/files/{file_id}")
async def delete_file_admin(file_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
        
    if file.file_path and os.path.exists(file.file_path):
        try:
            os.remove(file.file_path)
        except:
            pass
            
    db.delete(file)
    _log(db, admin["user_id"], "delete_file", file_id, f"Deleted file {file.filename}")
    db.commit()
    return {"message": "File deleted"}

@router.delete("/reviews/{review_id}")
async def delete_review_admin(review_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    review = db.query(CodeReview).filter(CodeReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    _log(db, admin["user_id"], "delete_review", review_id, f"Deleted review {review_id}")
    db.commit()
    return {"message": "Review deleted"}

@router.delete("/chats/{chat_id}")
async def delete_chat_admin(chat_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    chat = db.query(ChatMessage).filter(ChatMessage.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(chat)
    _log(db, admin["user_id"], "delete_chat", chat_id, f"Deleted chat {chat_id}")
    db.commit()
    return {"message": "Chat deleted"}

@router.delete("/activity/{activity_id}")
async def delete_activity_admin(activity_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    act = db.query(Activity).filter(Activity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(act)
    _log(db, admin["user_id"], "delete_activity", activity_id, f"Deleted activity {activity_id}")
    db.commit()
    return {"message": "Activity deleted"}

@router.delete("/login-history/{log_id}")
async def delete_login_admin(log_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    log = db.query(LoginHistory).filter(LoginHistory.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    db.delete(log)
    _log(db, admin["user_id"], "delete_login_log", log_id, f"Deleted login history {log_id}")
    db.commit()
    return {"message": "Login log deleted"}

@router.delete("/logs/{log_id}")
async def delete_admin_log_admin(log_id: int, admin=Depends(admin_only), db: Session = Depends(get_db)):
    log = db.query(AdminLog).filter(AdminLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    db.delete(log)
    db.commit()
    return {"message": "Admin log deleted"}
