from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import Project, ProjectCollaborator
from .auth import verify_token

def get_project_role(project_id: int, user_id: int, db: Session):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    if project.owner_id == user_id:
        return "OWNER"
        
    collab = db.query(ProjectCollaborator).filter(
        ProjectCollaborator.project_id == project_id,
        ProjectCollaborator.user_id == user_id
    ).first()
    
    if collab:
        return collab.role
        
    return None

def check_role(min_role: str):
    def role_dependency(
        project_id: int, 
        current_user = Depends(verify_token), 
        db: Session = Depends(get_db)
    ):
        if current_user.get("role") == "admin":
            return current_user
            
        role = get_project_role(project_id, current_user["user_id"], db)
        if not role:
            raise HTTPException(status_code=403, detail="Access denied. Not a collaborator.")
            
        role_hierarchy = {"READ": 1, "TRIAGE": 2, "WRITE": 3, "MAINTAIN": 4, "ADMIN": 5, "OWNER": 6}
        
        if role_hierarchy.get(role, 0) < role_hierarchy.get(min_role, 0):
            raise HTTPException(status_code=403, detail=f"Requires {min_role} role")
            
        return current_user
    return role_dependency

def verify_user_role(project_id: int, min_role: str, current_user: dict, db: Session):
    if current_user.get("role") == "admin":
        return
        
    role = get_project_role(project_id, current_user["user_id"], db)
    if not role:
        raise HTTPException(status_code=403, detail="Access denied. Not a collaborator.")
        
    role_hierarchy = {"READ": 1, "TRIAGE": 2, "WRITE": 3, "MAINTAIN": 4, "ADMIN": 5, "OWNER": 6}
    if role_hierarchy.get(role, 0) < role_hierarchy.get(min_role, 0):
        raise HTTPException(status_code=403, detail=f"Requires {min_role} role")

