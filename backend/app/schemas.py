from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Register(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: Optional[str] = "user"

class Login(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class Response(BaseModel):
    id: int
    username: str
    email: str
    role: str
    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    name: str
    description: str
    github_token: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    class Config:
        from_attributes = True

class FileResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_path: str
    folder: Optional[str] = "/"
    class Config:
        from_attributes = True

class FileRenameRequest(BaseModel):
    new_filename: str

class FileMoveRequest(BaseModel):
    new_folder: str

class FolderCreate(BaseModel):
    name: str
    parent: Optional[str] = "/"

class ChatCreate(BaseModel):
    project_id: int
    message: str

class CommentCreate(BaseModel):
    project_id: int
    file_id: int
    comment: str

class CommitCreate(BaseModel):
    file_id: int
    commit_message: str

class RollbackRequest(BaseModel):
    version_id: int

class AdminUserAction(BaseModel):
    user_id: int

class ProfileUpdate(BaseModel):
    username: str
    email: EmailStr

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

