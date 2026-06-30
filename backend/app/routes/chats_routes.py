from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import ChatMessage, Comment, Notification, Activity
from ..schemas import ChatCreate, CommentCreate
from ..auth import verify_token
from ..permissions import verify_user_role
from ..websocket.socket_manager import sio

router = APIRouter()

@router.post("/chat")
async def send_chat(
    chat: ChatCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        msg = ChatMessage(
            project_id = chat.project_id,
            sender_id  = current_user["user_id"],
            username   = current_user.get("username", ""),
            message    = chat.message,
            created_at = datetime.now()
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        payload = {
            "id":         msg.id,
            "project_id": msg.project_id,
            "sender_id":  msg.sender_id,
            "username":   msg.username,
            "message":    msg.message,
            "is_pinned":  msg.is_pinned,
            "timestamp":  msg.created_at.isoformat()
        }

        try:
            await sio.emit("chat_message", payload, room=f"project_{chat.project_id}")
            await sio.emit("notification", {
                "type": "chat_message",
                "message": f"New message from {msg.username} in Project #{chat.project_id}",
                "project_id": chat.project_id,
                "msg_id": msg.id
            })
        except Exception:
            pass

        return {"message": "Chat Saved", "id": msg.id}
    except Exception as exc:
        print(f"[chat/post] error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.get("/chat/{project_id}")
def get_chat(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Load full message history for a project room. No auth required for reading."""
    try:
        chats = db.query(ChatMessage).filter(
            ChatMessage.project_id == project_id
        ).order_by(ChatMessage.created_at.asc()).all()

        return [
            {
                "id":         c.id,
                "project_id": c.project_id,
                "sender_id":  c.sender_id,
                "username":   c.username or f"User #{c.sender_id}",
                "message":    c.message,
                "is_pinned":  c.is_pinned,
                "timestamp":  c.created_at.isoformat() if c.created_at else ""
            }
            for c in chats
        ]
    except Exception as exc:
        print(f"[chat/{project_id}] error: {exc}")
        return []

@router.delete("/chat/{message_id}")
async def delete_chat_message(
    message_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
            
        project_id = msg.project_id
        verify_user_role(project_id, "READ", current_user, db)
        
        db.delete(msg)
        db.commit()
        
        try:
            await sio.emit("message_deleted", {"id": message_id, "project_id": project_id}, room=f"project_{project_id}")
        except Exception:
            pass
            
        return {"message": "Message deleted"}
    except Exception as exc:
        db.rollback()
        print(f"[chat/delete] error: {exc}")
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail="Failed to delete message")

@router.patch("/chat/{message_id}/pin")
async def toggle_pin_chat(
    message_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    msg.is_pinned = not msg.is_pinned
    db.commit()
    
    payload = {
        "id": msg.id,
        "project_id": msg.project_id,
        "is_pinned": msg.is_pinned
    }
    try:
        await sio.emit("message_pinned", payload, room=f"project_{msg.project_id}")
    except Exception:
        pass

    return {"message": "Chat pin status updated", "is_pinned": msg.is_pinned}

@router.post("/comment")
async def add_comment(
    comment: CommentCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    new_comment = Comment(
        project_id = comment.project_id,
        file_id    = comment.file_id,
        user_id    = current_user["user_id"],
        comment    = comment.comment,
        created_at = datetime.now()
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    payload = {
        "id":         new_comment.id,
        "project_id": new_comment.project_id,
        "file_id":    new_comment.file_id,
        "user_id":    new_comment.user_id,
        "username":   current_user.get("username", f"User #{new_comment.user_id}"),
        "comment":    new_comment.comment,
        "timestamp":  new_comment.created_at.isoformat()
    }

    try:
        await sio.emit("comment_added", payload, room=f"project_{comment.project_id}")
    except Exception:
        pass

    return {"message": "Comment Added", "id": new_comment.id}


@router.get("/comments/{file_id}")
def get_comments(file_id: int, db: Session = Depends(get_db)):
    from ..models import User
    comments = db.query(Comment).filter(
        Comment.file_id == file_id
    ).order_by(Comment.created_at.asc()).all()

    result = []
    for c in comments:
        user = db.query(User).filter(User.id == c.user_id).first()
        result.append({
            "id":         c.id,
            "project_id": c.project_id,
            "file_id":    c.file_id,
            "user_id":    c.user_id,
            "username":   user.username if user else f"User #{c.user_id}",
            "comment":    c.comment,
            "timestamp":  c.created_at.isoformat() if c.created_at else ""
        })
    return result

@router.get("/comments/project/{project_id}")
def get_project_comments(
    project_id: int, 
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    verify_user_role(project_id, "READ", current_user, db)
    from ..models import User
    comments = db.query(Comment).filter(
        Comment.project_id == project_id
    ).order_by(Comment.created_at.asc()).all()

    result = []
    for c in comments:
        user = db.query(User).filter(User.id == c.user_id).first()
        result.append({
            "id":         c.id,
            "project_id": c.project_id,
            "file_id":    c.file_id,
            "user_id":    c.user_id,
            "username":   user.username if user else f"User #{c.user_id}",
            "comment":    c.comment,
            "timestamp":  c.created_at.isoformat() if c.created_at else ""
        })
    return result

async def _create_notification_safe(
    db: Session,
    user_id: int,
    message: str,
    notif_type: str = "info",
    sio_room: str = None,
) -> None:
    """
    Insert a notification only if an identical one does not already exist.
    Duplicate = same user_id + message + notif_type.
    """
    existing = db.query(Notification).filter(
        Notification.user_id    == user_id,
        Notification.message    == message,
        Notification.notif_type == notif_type,
    ).first()

    if existing:
        return  

    notif = Notification(
        user_id    = user_id,
        message    = message,
        notif_type = notif_type,
        created_at = datetime.utcnow()
    )
    try:
        db.add(notif)
        db.commit()
        db.refresh(notif)
    except IntegrityError:
        db.rollback()
        return  

    if sio_room:
        try:
            await sio.emit("notification", {
                "id":        notif.id,
                "type":      notif_type,
                "message":   message,
                "user_id":   user_id,
                "is_read":   False,
                "timestamp": notif.created_at.isoformat()
            }, room=sio_room)
        except Exception:
            pass

@router.post("/notify")
async def create_notification(
    user_id: int,
    message: str,
    notif_type: str = "info",
    db: Session = Depends(get_db)
):
    await _create_notification_safe(
        db=db,
        user_id=user_id,
        message=message,
        notif_type=notif_type,
        sio_room=f"user_{user_id}",
    )
    return {"message": "Notification created"}

@router.get("/notifications/{user_id}")
def get_notifications(user_id: int, db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(Notification.created_at.desc()).all()

    return [
        {
            "id":        n.id,
            "message":   n.message,
            "notif_type": n.notif_type,
            "is_read":   n.is_read,
            "timestamp": n.created_at.isoformat() if n.created_at else ""
        }
        for n in notifs
    ]

@router.get("/notifications/{user_id}/unread-count")
def unread_count(user_id: int, db: Session = Depends(get_db)):
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()
    return {"unread": count}

@router.patch("/notifications/{notif_id}/read")
def mark_read(
    notif_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
    Notification.id == notif_id,
    Notification.user_id == current_user["user_id"]
).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Marked as read"}

@router.patch("/notifications/{user_id}/read-all")
def mark_all_read(
    user_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_user["user_id"],
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

@router.get("/activity-feed")
def activity_feed(db: Session = Depends(get_db)):
    activities = db.query(Activity).order_by(
        Activity.timestamp.desc()
    ).limit(50).all()

    return [
        {
            "id":         a.id,
            "action":     a.action,
            "project_id": a.project_id,
            "user_id":    a.user_id,
            "timestamp":  a.timestamp.isoformat() if a.timestamp else ""
        }
        for a in activities
    ]
