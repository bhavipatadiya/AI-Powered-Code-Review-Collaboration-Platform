import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..ai.ai_reviewer import generate_review
from ..models import Project, ProjectFile, Activity, RepoFolder
from ..schemas import ProjectCreate, FolderCreate, FileRenameRequest, FileMoveRequest
from ..auth import verify_token
from ..permissions import verify_user_role
from ..services.pinecone_service import store_vectors

import requests
import base64
from dotenv import dotenv_values

router = APIRouter()
MODIFIED_DIFFS = {}

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".java", ".cpp", ".c", ".ts",
    ".html", ".css", ".json", ".txt", ".cs",
}

@router.post("/create")
def create_project(
    project: ProjectCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    print("CURRENT USER =", current_user)

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    env_dict = dotenv_values(env_path) if os.path.exists(env_path) else {}

    github_token = os.getenv("GITHUB_TOKEN") or env_dict.get("GITHUB_TOKEN") or project.github_token
    github_link = os.getenv("GITHUB_LINK") or env_dict.get("GITHUB_LINK")

    if not github_token or not github_link:
        raise HTTPException(
            status_code=500,
            detail="GitHub is not configured. Set GITHUB_TOKEN and GITHUB_LINK in .env"
        )

    github_username = github_link.rstrip("/").split("/")[-1]

    github_url = None
    github_error = None

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    repo_data = {
        "name": project.name.replace(" ", "-").lower(),
        "description": project.description,
        "private": True,
        "auto_init": True
    }
    try:
        r = requests.post("https://api.github.com/user/repos", json=repo_data, headers=headers)
        if r.status_code in (201, 200):
            github_url = r.json().get("full_name")
        else:
            try:
                github_error = r.json().get("message")
            except ValueError:
                github_error = r.text if r.text else "Unknown error"
    except requests.RequestException as e:
        github_error = str(e)

    if not github_url:
        github_url = f"{github_username}/{project.name.replace(' ', '-').lower()}"

    new_project = Project(
        name        = project.name,
        description = project.description,
        owner_id    = current_user["user_id"],
        github_token = github_token,
        github_repo_url = github_url
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    db.add(Activity(action="Created Project", project_id=new_project.id, user_id=current_user["user_id"]))
    db.commit()

    os.makedirs(f"uploads/project_{new_project.id}", exist_ok=True)

    msg = "Project Created"
    if github_url:
        msg += f" with GitHub repo: {github_url}"
    elif github_error:
        msg += f". (GitHub Warning: {github_error})"
    return {"message": msg, "project_id": new_project.id}

@router.get("/my-projects")
def my_projects(current_user=Depends(verify_token), db: Session = Depends(get_db)):
    user_id = current_user["user_id"]
    
    owned = db.query(Project).filter(Project.owner_id == user_id).all()
    
    from ..models import ProjectCollaborator, User
    collab_links = db.query(ProjectCollaborator).filter(ProjectCollaborator.user_id == user_id).all()
    
    owned_out = [{
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at,
        "owner_id": p.owner_id,
        "github_repo_url": p.github_repo_url
    } for p in owned]
    
    invited_out = []
    for c in collab_links:
        p = db.query(Project).filter(Project.id == c.project_id).first()
        if p:
            owner = db.query(User).filter(User.id == p.owner_id).first()
            invited_out.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at,
                "owner_id": p.owner_id,
                "owner_name": owner.username if owner else "Unknown",
                "role": c.role,
                "github_repo_url": p.github_repo_url
            })
            
    return {"owned": owned_out, "invited": invited_out}

@router.post("/upload/{project_id}")
def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    folder: str = Query(default="/"),
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project Not Found")

    verify_user_role(project_id, "WRITE", current_user, db)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    project_folder = f"uploads/project_{project_id}"
    os.makedirs(project_folder, exist_ok=True)

    base_path = os.path.join(project_folder, file.filename)
    file_path = base_path
    counter   = 1
    while os.path.exists(file_path):
        name, ext2 = os.path.splitext(file.filename)
        file_path = os.path.join(project_folder, f"{name}_{counter}{ext2}")
        counter += 1

    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    if project.github_token and project.github_repo_url:
        gh_headers = {
            "Authorization": f"token {project.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        gh_path = f"{folder.strip('/')}/{file.filename}".strip('/') if folder and folder != "/" else file.filename
        gh_url = f"https://api.github.com/repos/{project.github_repo_url}/contents/{gh_path}"
        gh_data = {
            "message": f"Upload {file.filename}",
            "content": base64.b64encode(content).decode("utf-8")
        }
        try:
            get_r = requests.get(gh_url, headers=gh_headers)
            if get_r.status_code == 200:
                gh_data["sha"] = get_r.json().get("sha")
            put_r = requests.put(gh_url, json=gh_data, headers=gh_headers)
            if put_r.status_code not in (200, 201):
                try:
                    error_msg = put_r.json().get("message")
                except ValueError:
                    error_msg = put_r.text if put_r.text else "Unknown error"
                raise HTTPException(status_code=400, detail=f"GitHub commit failed: {error_msg}")
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"GitHub API error: {str(e)}")

    new_file = ProjectFile(
        filename   = os.path.basename(file_path),
        file_type  = ext,
        file_path  = file_path,
        folder     = folder,
        project_id = project_id
    )
    db.add(new_file)

    db.add(Activity(
        action     = f"Uploaded {file.filename}",
        project_id = project_id,
        user_id    = current_user["user_id"]
    ))
    db.commit()
    db.refresh(new_file)

    pinecone_stored = False
    vector_count = 0
    try:
        if ext in [".py", ".js", ".html", ".css", ".txt", ".md", ".json", ".ts", ".java", ".c", ".cpp"]:
            try:
                decoded_content = content.decode('utf-8')
                from ..services.pinecone_service import split_into_chunks
                chunks = split_into_chunks(decoded_content)
                vector_count = len(chunks)
                store_vectors(project_id, current_user["user_id"], new_file.id, new_file.filename, new_file.file_path, decoded_content)
                pinecone_stored = True
            except UnicodeDecodeError:
                pass
    except Exception as e:
        print(f"Failed to store vectors: {e}")

    return {"message": "File uploaded successfully", "file_id": new_file.id, "pinecone_stored": pinecone_stored, "vector_count": vector_count}

@router.get("/{project_id}/pinecone_stats")
def get_pinecone_stats(project_id: int, db: Session = Depends(get_db)):
    from ..services.pinecone_service import _get_index, PINECONE_INDEX_NAME
    idx = _get_index()
    if not idx:
        return {"status": "error", "message": "Pinecone not initialized"}
    
    try:
        stats = idx.describe_index_stats()
        return {
            "status": "success",
            "index_name": PINECONE_INDEX_NAME,
            "total_vector_count": stats.total_vector_count,
            "dimension": stats.dimension
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/{project_id}/files")
def get_project_files(
    project_id: int,
    folder: str = Query(default=None),
    db: Session = Depends(get_db)
):
    q = db.query(ProjectFile).filter(ProjectFile.project_id == project_id)
    if folder:
        q = q.filter(ProjectFile.folder == folder)
    return q.all()

@router.patch("/files/{file_id}/rename")
def rename_file(
    file_id: int,
    body: FileRenameRequest,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    f = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(f.project_id, "MAINTAIN", current_user, db)

    old_path = f.file_path
    new_path = os.path.join(os.path.dirname(old_path), body.new_filename)

    if os.path.exists(old_path):
        os.rename(old_path, new_path)

    f.filename  = body.new_filename
    f.file_path = new_path
    db.add(Activity(action=f"Renamed file to {body.new_filename}", project_id=f.project_id, user_id=current_user["user_id"]))
    db.commit()
    return {"message": "File renamed", "new_filename": body.new_filename}

@router.patch("/files/{file_id}/move")
def move_file(
    file_id: int,
    body: FileMoveRequest,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    f = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(f.project_id, "MAINTAIN", current_user, db)

    f.folder = body.new_folder
    db.add(Activity(action=f"Moved {f.filename} to {body.new_folder}", project_id=f.project_id, user_id=current_user["user_id"]))
    db.commit()
    return {"message": "File moved", "new_folder": body.new_folder}

@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    f = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(f.project_id, "MAINTAIN", current_user, db)

    if os.path.exists(f.file_path):
        os.remove(f.file_path)

    db.add(Activity(action=f"Deleted {f.filename}", project_id=f.project_id, user_id=current_user["user_id"]))
    db.delete(f)
    db.commit()
    return {"message": "File deleted"}

@router.post("/{project_id}/folders")
def create_folder(
    project_id: int,
    body: FolderCreate,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    verify_user_role(project_id, "MAINTAIN", current_user, db)

    folder = RepoFolder(
        project_id = project_id,
        name       = body.name,
        parent     = body.parent
    )
    db.add(folder)
    db.add(Activity(action=f"Created folder {body.name}", project_id=project_id, user_id=current_user["user_id"]))
    db.commit()
    return {"message": "Folder created", "folder_id": folder.id, "name": folder.name}


@router.get("/{project_id}/folders")
def get_folders(project_id: int, db: Session = Depends(get_db)):
    folders = db.query(RepoFolder).filter(RepoFolder.project_id == project_id).all()
    return [{"id": f.id, "name": f.name, "parent": f.parent} for f in folders]


@router.delete("/folders/{folder_id}")
def delete_folder(
    folder_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    folder = db.query(RepoFolder).filter(RepoFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    verify_user_role(folder.project_id, "MAINTAIN", current_user, db)

    db.add(Activity(action=f"Deleted folder {folder.name}", project_id=folder.project_id, user_id=current_user["user_id"]))
    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted"}

@router.get("/{project_id}/activities")
def get_activities(project_id: int, db: Session = Depends(get_db)):
    from ..models import User
    activities = db.query(Activity, User.username).outerjoin(User, Activity.user_id == User.id).filter(
        Activity.project_id == project_id
    ).order_by(Activity.timestamp.desc()).all()
    
    return [
        {
            "id": a.Activity.id,
            "action": a.Activity.action,
            "timestamp": a.Activity.timestamp.isoformat(),
            "username": a.username or f"User #{a.Activity.user_id}"
        } for a in activities
    ]

@router.get("/files/{file_id}/content")
def get_file_content(
    file_id: int,
    db: Session = Depends(get_db)
):
    f = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not f:
        return {
            "id":          file_id,
            "filename":    "",
            "file_name":   "",
            "file_path":   "",
            "file_type":   "",
            "folder":      "/",
            "uploaded_at": "",
            "content":     "",
            "lines":       0,
            "project_id":  0,
        }

    path = f.file_path
    content = ""
    if path:
        if not os.path.exists(path):
            if os.path.exists(os.path.join("backend", path)):
                path = os.path.join("backend", path)
            elif (path.startswith("backend/") or path.startswith("backend\\")) and os.path.exists(path[8:]):
                path = path[8:]
            else:
                cand1 = os.path.join("backend", "uploads", f"project_{f.project_id}", f.filename)
                cand2 = os.path.join("uploads", f"project_{f.project_id}", f.filename)
                if os.path.exists(cand1):
                    path = cand1
                elif os.path.exists(cand2):
                    path = cand2

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except Exception as e:
                print(f"Could not read file {path}: {e}")

    return {
        "id":          f.id,
        "filename":    f.filename,
        "file_name":   f.filename,
        "file_path":   f.file_path,
        "file_type":   f.file_type,
        "folder":      f.folder or "/",
        "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else "",
        "content":     content,
        "lines":       content.count("\n") + 1,
        "project_id":  f.project_id,
    }

from pydantic import BaseModel as _BM

class FileSaveRequest(_BM):
    content: str

@router.put("/files/{file_id}/content")
def save_file_content(
    file_id: int,
    body: FileSaveRequest,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Write new content back to disk. Does NOT create a version — user must commit explicitly."""
    f = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    verify_user_role(f.project_id, "WRITE", current_user, db)

    old_content = ""
    try:
        path = f.file_path
        if not os.path.exists(path):
            if os.path.exists(os.path.join("backend", path)):
                path = os.path.join("backend", path)
            elif (path.startswith("backend/") or path.startswith("backend\\")) and os.path.exists(path[8:]):
                path = path[8:]
            else:
                cand1 = os.path.join("backend", "uploads", f"project_{f.project_id}", f.filename)
                cand2 = os.path.join("uploads", f"project_{f.project_id}", f.filename)
                if os.path.exists(cand1):
                    path = cand1
                elif os.path.exists(cand2):
                    path = cand2

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                old_content = fh.read()
    except Exception:
        pass

    import difflib
    diff = list(difflib.unified_diff(
        old_content.splitlines(),
        body.content.splitlines(),
        fromfile=f.filename + " (old)",
        tofile=f.filename + " (new)",
        lineterm=""
    ))
    diff_text = "\n".join(diff)
    MODIFIED_DIFFS[file_id] = diff_text

    try:
        write_path = f.file_path
        if not os.path.exists(os.path.dirname(write_path)):
            if os.path.exists(os.path.join("backend", os.path.dirname(write_path))):
                write_path = os.path.join("backend", write_path)
        with open(write_path, "w", encoding="utf-8") as fh:
            fh.write(body.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not write file: {e}")

    project = db.query(Project).filter(Project.id == f.project_id).first()
    if project and project.github_token and project.github_repo_url:
        gh_headers = {
            "Authorization": f"token {project.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        final_name = f.filename
        gh_url = f"https://api.github.com/repos/{project.github_repo_url}/contents/{final_name}"
        gh_data = {
            "message": f"Update {f.filename}",
            "content": base64.b64encode(body.content.encode("utf-8")).decode("utf-8")
        }
        try:
            get_r = requests.get(gh_url, headers=gh_headers)
            if get_r.status_code == 200:
                gh_data["sha"] = get_r.json().get("sha")
            put_r = requests.put(gh_url, json=gh_data, headers=gh_headers)
            if put_r.status_code not in (200, 201):
                try:
                    error_msg = put_r.json().get("message")
                except ValueError:
                    error_msg = put_r.text if put_r.text else "Unknown error"
                raise HTTPException(status_code=400, detail=f"GitHub commit failed: {error_msg}")
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"GitHub API error: {str(e)}")

    f.needs_review = True
    from datetime import datetime
    f.last_modified = datetime.utcnow()

    db.add(Activity(
        action     = f"Edited {f.filename}",
        project_id = f.project_id,
        user_id    = current_user["user_id"]
    ))
    db.commit()

    try:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in [".py", ".js", ".html", ".css", ".txt", ".md", ".json", ".ts", ".java", ".c", ".cpp"]:
            store_vectors(f.project_id, current_user["user_id"], f.id, f.filename, f.file_path, body.content)
    except Exception as e:
        print(f"Failed to store vectors on save: {e}")

    return {
        "message":  "File saved",
        "filename": f.filename,
        "lines":    body.content.count("\n") + 1,
    }

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user["user_id"]
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")

    db.query(ProjectFile).filter(ProjectFile.project_id == project_id).delete()
    db.query(Activity).filter(Activity.project_id == project_id).delete()
    db.query(RepoFolder).filter(RepoFolder.project_id == project_id).delete()
    db.delete(project)
    db.commit()

    folder_path = f"uploads/project_{project_id}"
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)

    return {"message": "Project deleted"}

@router.get("/review/{project_id}")
def review_project(
    project_id: int,
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    if not files:
        raise HTTPException(status_code=404, detail="No files found")

    code_content = ""
    for f in files:
        try:
            with open(f.file_path, "r", encoding="utf-8", errors="ignore") as fh:
                code_content += fh.read() + "\n\n"
        except Exception:
            pass

    review = generate_review(code_content)
    return {"project_id": project_id, "review": review}
