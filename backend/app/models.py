from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, UniqueConstraint
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    username   = Column(String,  unique=True, nullable=False)
    email      = Column(String,  unique=True, nullable=False)
    password   = Column(String,  nullable=False)
    role       = Column(String,  default="user")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String,  nullable=False)
    description = Column(String,  default="")
    owner_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    github_token    = Column(String,  nullable=True)
    github_repo_url = Column(String,  nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

class ProjectFile(Base):
    __tablename__ = "project_files"

    id          = Column(Integer, primary_key=True, index=True)
    filename    = Column(String)
    file_type   = Column(String)
    file_path   = Column(String)
    folder      = Column(String, default="/")
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    needs_review = Column(Boolean, default=False)
    last_modified = Column(DateTime, nullable=True)


class Activity(Base):
    __tablename__ = "activities"

    id         = Column(Integer, primary_key=True)
    action     = Column(String)
    project_id = Column(Integer)
    user_id    = Column(Integer)
    timestamp  = Column(DateTime, default=datetime.utcnow)


class CodeReview(Base):
    __tablename__ = "code_reviews"

    id                       = Column(Integer, primary_key=True)
    project_id               = Column(Integer)
    file_id                  = Column(Integer)
    issues                   = Column(Text)
    suggestions              = Column(Text)
    documentation            = Column(Text)
    bad_practices            = Column(Text)
    performance_improvements = Column(Text)
    generated_comments       = Column(Text)
    score                    = Column(Integer, default=0)
    created_at               = Column(DateTime, default=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id         = Column(Integer, primary_key=True)
    project_id = Column(Integer)
    sender_id  = Column(Integer)
    username   = Column(String, default="")
    message    = Column(String)
    is_pinned  = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Comment(Base):
    __tablename__ = "comments"

    id         = Column(Integer, primary_key=True)
    project_id = Column(Integer)
    file_id    = Column(Integer)
    user_id    = Column(Integer)
    comment    = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer)
    message    = Column(String)
    notif_type = Column(String, default="info")
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "message", "notif_type", name="uq_notification"),
    )

class FileVersion(Base):
    __tablename__ = "file_versions"

    id             = Column(Integer, primary_key=True)
    file_id        = Column(Integer)
    project_id     = Column(Integer)
    version_number = Column(Integer)
    commit_message = Column(String)
    snapshot_path  = Column(String)
    created_by     = Column(Integer)
    author         = Column(String, default="")
    created_at     = Column(DateTime, default=datetime.utcnow)

class CommitHistory(Base):
    __tablename__ = "commit_history"

    id             = Column(Integer, primary_key=True)
    project_id     = Column(Integer)
    user_id        = Column(Integer)
    author         = Column(String, default="")
    commit_message = Column(String)
    created_at     = Column(DateTime, default=datetime.utcnow)

class RollbackHistory(Base):
    """Tracks every rollback operation for audit trail."""
    __tablename__ = "rollback_history"

    id             = Column(Integer, primary_key=True)
    file_id        = Column(Integer)
    project_id     = Column(Integer)
    version_id     = Column(Integer)
    version_number = Column(Integer)
    rolled_back_by = Column(Integer)   # user_id
    rolled_back_at = Column(DateTime, default=datetime.utcnow)

class LoginHistory(Base):
    __tablename__ = "login_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    ip_address = Column(String, default="")
    user_agent = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class AdminLog(Base):
    __tablename__ = "admin_logs"

    id         = Column(Integer, primary_key=True)
    admin_id   = Column(Integer, ForeignKey("users.id"))
    action     = Column(String)
    target_id  = Column(Integer, nullable=True)
    detail     = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class RepoFolder(Base):
    __tablename__ = "repo_folders"

    id         = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    name       = Column(String, nullable=False)
    parent     = Column(String, default="/")
    created_at = Column(DateTime, default=datetime.utcnow)

class ProjectCollaborator(Base):
    __tablename__ = "project_collaborators"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    role       = Column(String, default="READ")
    added_by   = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    invitee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    status     = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id         = Column(Integer, primary_key=True)
    project_id = Column(Integer)
    user_id    = Column(Integer)
    question   = Column(String)
    answer     = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
