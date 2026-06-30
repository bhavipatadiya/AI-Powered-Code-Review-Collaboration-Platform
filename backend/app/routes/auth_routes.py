from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import User, LoginHistory
from ..schemas import Register
from ..utils.security import hash_password, verify_password
from ..auth import create_access_token, verify_token, admin_only

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register(user: Register, db: Session = Depends(get_db)):

    admin_exists = db.query(User).filter(User.role == "admin").first()

    if user.role.lower() == "admin":
        if admin_exists:
          
            raise HTTPException(
                status_code=403,
                detail="An admin account already exists. You cannot register as admin."
            )
        assigned_role = "admin"
    else:
        assigned_role = user.role

    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = User(
        username  = user.username,
        email     = user.email,
        password  = hash_password(user.password),
        role      = assigned_role,
        is_active = True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if assigned_role == "admin":
        return {
            "message": "Admin account created. You are the platform administrator.",
            "role": "admin"
        }

    return {"message": "User registered successfully", "role": assigned_role}


@router.post("/login", description="Enter your EMAIL in the username field.")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account has been disabled. Please contact the administrator."
        )

    try:
        log = LoginHistory(
            user_id    = user.id,
            ip_address = request.client.host if request.client else "",
            user_agent = request.headers.get("user-agent", "")[:200],
        )
        db.add(log)
        db.commit()
    except Exception:
        pass  

    token = create_access_token(data={
        "user_id":  user.id,
        "username": user.username,
        "email":    user.email,
        "role":     user.role,
    })

    return {"access_token": token, "token_type": "bearer"}


from ..schemas import ProfileUpdate, PasswordUpdate

@router.get("/profile")
def user_profile(current_user=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}

@router.put("/profile")
def update_profile(data: ProfileUpdate, current_user=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if data.email != user.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already taken")
        
    if data.username != user.username and db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
        
    user.username = data.username
    user.email = data.email
    db.commit()
    return {"message": "Profile updated", "username": user.username, "email": user.email}

@router.put("/profile/password")
def change_password(data: PasswordUpdate, current_user=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not verify_password(data.old_password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    user.password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@router.delete("/profile")
def delete_account(current_user=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    from ..models import (
        LoginHistory, Activity, AdminLog, CommitHistory, RollbackHistory,
        ProjectCollaborator, ProjectInvitation, Comment, ChatMessage, Notification,
        Project, ProjectFile, RepoFolder, FileVersion, CodeReview
    )
    uid = user.id
    
    try:
        db.query(LoginHistory).filter(LoginHistory.user_id == uid).delete()
        db.query(Activity).filter(Activity.user_id == uid).delete()
        db.query(AdminLog).filter(AdminLog.admin_id == uid).delete()
        db.query(CommitHistory).filter(CommitHistory.user_id == uid).delete()
        db.query(RollbackHistory).filter(RollbackHistory.rolled_back_by == uid).delete()
        db.query(ProjectCollaborator).filter((ProjectCollaborator.user_id == uid) | (ProjectCollaborator.added_by == uid)).delete()
        db.query(ProjectInvitation).filter((ProjectInvitation.inviter_id == uid) | (ProjectInvitation.invitee_id == uid)).delete()
        db.query(Comment).filter(Comment.user_id == uid).delete()
        db.query(ChatMessage).filter(ChatMessage.sender_id == uid).delete()
        db.query(Notification).filter(Notification.user_id == uid).delete()
        db.query(FileVersion).filter(FileVersion.created_by == uid).delete()

        projects = db.query(Project).filter(Project.owner_id == uid).all()
        for p in projects:
            db.query(CodeReview).filter(CodeReview.project_id == p.id).delete()
            db.query(ProjectFile).filter(ProjectFile.project_id == p.id).delete()
            db.query(RepoFolder).filter(RepoFolder.project_id == p.id).delete()
            db.query(Activity).filter(Activity.project_id == p.id).delete()
            db.delete(p)
            
        db.delete(user)
        db.commit()
        return {"message": "Account deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


@router.get("/admin")
def admin_dashboard(admin=Depends(admin_only)):
    return {"message": "Welcome Admin", "admin": admin}
