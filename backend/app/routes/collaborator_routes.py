from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Project, ProjectCollaborator, ProjectInvitation, Activity, Notification
from ..auth import verify_token
from ..permissions import check_role

router = APIRouter()

@router.get("/projects/{project_id}/collaborators")
def get_collaborators(
    project_id: int,
    db: Session = Depends(get_db),
    _=Depends(check_role("READ"))
):
    project = db.query(Project).filter(Project.id == project_id).first()
    owner = db.query(User).filter(User.id == project.owner_id).first()
    
    collabs = db.query(ProjectCollaborator).filter(ProjectCollaborator.project_id == project_id).all()
    
    result = [{
        "id": owner.id,
        "username": owner.username,
        "email": owner.email,
        "role": "OWNER",
        "joined_at": project.created_at.isoformat(),
        "status": "Active"
    }]
    
    for c in collabs:
        user = db.query(User).filter(User.id == c.user_id).first()
        result.append({
            "id": c.user_id,
            "username": user.username,
            "email": user.email,
            "role": c.role,
            "joined_at": c.created_at.isoformat(),
            "status": "Active"
        })
        
    return result

@router.get("/users/search")
def search_users(
    q: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(verify_token)
):
    users = db.query(User).filter(
        (User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")),
        User.id != current_user["user_id"]
    ).limit(10).all()
    
    return [{"id": u.id, "username": u.username, "email": u.email} for u in users]

@router.post("/projects/{project_id}/invitations")
def send_invitation(
    project_id: int,
    invitee_id: int = Body(...),
    role: str = Body("READ"),
    db: Session = Depends(get_db),
    current_user=Depends(check_role("OWNER"))
):

    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )


    user = db.query(User).filter(
        User.id == invitee_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


    existing = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == invitee_id
    ).first()


    if existing:
        raise HTTPException(
            status_code=400,
            detail="User already collaborator"
        )


    pending = db.query(ProjectInvitation).filter(
        ProjectInvitation.project_id == project_id,
        ProjectInvitation.invitee_id == invitee_id,
        ProjectInvitation.status == "pending"
    ).first()


    if pending:
        raise HTTPException(
            status_code=400,
            detail="Invitation already sent"
        )


    new_inv = ProjectInvitation(
        project_id=project_id,
        inviter_id=current_user["user_id"],
        invitee_id=invitee_id,
        status="pending",
        created_at=datetime.utcnow()
    )


    db.add(new_inv)


    db.add(Notification(
        user_id=invitee_id,
        message=f"You have been invited to join {project.name}",
        notif_type="invitation",
        created_at=datetime.utcnow()
    ))


    db.add(Activity(
        action=f"Invitation sent to {user.username}",
        project_id=project_id,
        user_id=current_user["user_id"],
        timestamp=datetime.utcnow()
    ))


    db.commit()


    return {
        "message":"Invitation sent successfully",
        "project":project.name,
        "user":user.username,
        "role":role
    }
    
@router.get("/invitations")
def my_invitations(
    db: Session = Depends(get_db),
    current_user=Depends(verify_token)
):
    invs = db.query(ProjectInvitation).filter(
        ProjectInvitation.invitee_id == current_user["user_id"],
        ProjectInvitation.status == "pending"
    ).all()
    
    res = []
    for i in invs:
        p = db.query(Project).filter(Project.id == i.project_id).first()
        u = db.query(User).filter(User.id == i.inviter_id).first()
        res.append({
            "id": i.id,
            "project_id": p.id,
            "project_name": p.name,
            "inviter_name": u.username,
            "created_at": i.created_at.isoformat()
        })
    return res

@router.post("/invitations/{inv_id}/accept")
def accept_invitation(
    inv_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token)
):
    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == inv_id).first()
    if not inv or inv.invitee_id != current_user["user_id"] or inv.status != "pending":
        raise HTTPException(status_code=404, detail="Invitation not found or invalid")
        
    inv.status = "accepted"
    
    collab = ProjectCollaborator(
        project_id=inv.project_id,
        user_id=inv.invitee_id,
        role="READ",
        added_by=inv.inviter_id,
        created_at=datetime.utcnow()
    )
    db.add(collab)
    db.add(Activity(
        action=f"User accepted invitation",
        project_id=inv.project_id,
        user_id=current_user["user_id"],
        timestamp=datetime.utcnow()
    ))
    db.commit()
    return {"message": "Accepted"}

@router.post("/invitations/{inv_id}/reject")
def reject_invitation(
    inv_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(verify_token)
):
    inv = db.query(ProjectInvitation).filter(ProjectInvitation.id == inv_id).first()
    if not inv or inv.invitee_id != current_user["user_id"] or inv.status != "pending":
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    inv.status = "rejected"
    db.add(Activity(
        action=f"User rejected invitation",
        project_id=inv.project_id,
        user_id=current_user["user_id"],
        timestamp=datetime.utcnow()
    ))
    db.commit()
    return {"message": "Rejected"}

@router.patch("/projects/{project_id}/collaborators/{user_id}/role")
def change_role(
    project_id: int,
    user_id: int,
    role: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(check_role("OWNER"))
):
    collab = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == user_id
    ).first()
    
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
        
    collab.role = role
    
    db.add(Activity(
        action=f"Changed role of user {user_id} to {role}",
        project_id=project_id,
        user_id=current_user["user_id"],
        timestamp=datetime.utcnow()
    ))
    
    db.commit()
    return {"message": "Role updated"}

@router.delete("/projects/{project_id}/collaborators/{user_id}")
def remove_collaborator(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role("OWNER"))
):
    collab = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == user_id
    ).first()
    
    if not collab:
        raise HTTPException(status_code=404, detail="Collaborator not found")
        
    db.delete(collab)
    
    db.add(Activity(
        action=f"Removed user {user_id} from project",
        project_id=project_id,
        user_id=current_user["user_id"],
        timestamp=datetime.utcnow()
    ))
    
    db.commit()
    return {"message": "Collaborator removed"}
