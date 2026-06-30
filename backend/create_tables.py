"""
Run this once to create / migrate all database tables.
    cd backend
    python create_tables.py

Safe to run multiple times — only creates tables/columns that are missing.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base
from app.models import (
    User, Project, ProjectFile, Activity,
    CodeReview, ChatMessage, Comment,
    Notification, FileVersion, CommitHistory,
    RollbackHistory, LoginHistory, AdminLog, RepoFolder
)
from sqlalchemy import inspect, text

print("Creating / migrating tables...")
Base.metadata.create_all(bind=engine)

inspector = inspect(engine)

def col_exists(table, col):
    return any(c["name"] == col for c in inspector.get_columns(table))

with engine.begin() as conn:

    if "code_reviews" in inspector.get_table_names() and not col_exists("code_reviews", "score"):
        conn.execute(text("ALTER TABLE code_reviews ADD COLUMN score INTEGER DEFAULT 0"))
        print("  + code_reviews.score")

  
    if "file_versions" in inspector.get_table_names() and not col_exists("file_versions", "author"):
        conn.execute(text("ALTER TABLE file_versions ADD COLUMN author VARCHAR DEFAULT ''"))
        print("  + file_versions.author")


    if "commit_history" in inspector.get_table_names() and not col_exists("commit_history", "author"):
        conn.execute(text("ALTER TABLE commit_history ADD COLUMN author VARCHAR DEFAULT ''"))
        print("  + commit_history.author")

    if "projects" in inspector.get_table_names() and not col_exists("projects", "github_token"):
        conn.execute(text("ALTER TABLE projects ADD COLUMN github_token VARCHAR"))
        print("  + projects.github_token")

    if "projects" in inspector.get_table_names() and not col_exists("projects", "github_repo_url"):
        conn.execute(text("ALTER TABLE projects ADD COLUMN github_repo_url VARCHAR"))
        print("  + projects.github_repo_url")

print("Done! All tables are up to date.")
