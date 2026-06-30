from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import verify_token
from ..models import (
    Project, ProjectFile, CodeReview, Activity,
    CommitHistory, ChatMessage, Comment, User,
    ProjectCollaborator
)
from ..services.analytics_service import calculate_loc, review_summary

router = APIRouter()

@router.get("/overview")
def dashboard_overview(
    current_user=Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Stats scoped to the logged-in user. New user sees 0 for everything."""
    try:
        user_id       = current_user["user_id"]
        owned_projects = db.query(Project).filter(Project.owner_id == user_id).all()
        collab_links = db.query(ProjectCollaborator).filter(ProjectCollaborator.user_id == user_id).all()
        collab_project_ids = [c.project_id for c in collab_links]
        collab_projects = db.query(Project).filter(Project.id.in_(collab_project_ids)).all() if collab_project_ids else []
        
        user_projects_dict = {p.id: p for p in (owned_projects + collab_projects)}
        user_projects = list(user_projects_dict.values())
        
        project_ids   = [p.id for p in user_projects]
        total_users   = db.query(User).count()

        if project_ids:
            files_count = db.query(ProjectFile).filter(ProjectFile.project_id.in_(project_ids)).count()
            reviews_count = db.query(CodeReview).filter(CodeReview.project_id.in_(project_ids)).count()
            commits_count = db.query(CommitHistory).filter(CommitHistory.project_id.in_(project_ids)).count()
            chats_count = db.query(ChatMessage).filter(ChatMessage.project_id.in_(project_ids)).count()
            
            total_issues = db.query(CodeReview).filter(
                CodeReview.project_id.in_(project_ids),
                CodeReview.issues != None,
                CodeReview.issues != ""
            ).count()
            total_suggestions = db.query(CodeReview).filter(
                CodeReview.project_id.in_(project_ids),
                CodeReview.suggestions != None,
                CodeReview.suggestions != ""
            ).count()
            rs = {
                "total_reviews": reviews_count,
                "total_issues": total_issues,
                "total_suggestions": total_suggestions
            }
            loc = files_count * 120
        else:
            files_count = reviews_count = commits_count = chats_count = 0
            rs = {"total_reviews": 0, "total_issues": 0, "total_suggestions": 0}
            loc = 0

        owned_details = []
        for p in user_projects:
            p_files    = db.query(ProjectFile).filter(ProjectFile.project_id == p.id).count()
            p_reviews  = db.query(CodeReview).filter(CodeReview.project_id == p.id).count()
            p_collabs  = db.query(ProjectCollaborator).filter(ProjectCollaborator.project_id == p.id).count()
            latest_act = db.query(Activity).filter(
                Activity.project_id == p.id
            ).order_by(Activity.id.desc()).first()

            owned_details.append({
                "name":              p.name,
                "created_at":        p.created_at.isoformat() if p.created_at else "",
                "files_count":       p_files,
                "reviews_count":     p_reviews,
                "collaborators_count": p_collabs,
                "latest_activity":   latest_act.action if latest_act else "No activity",
            })

        return {
            "total_users":            total_users,
            "projects":               len(user_projects),
            "files":                  files_count,
            "lines_of_code":          loc,
            "commits":                commits_count,
            "chat_messages":          chats_count,
            "review_summary":         rs,
            "most_common_issues":     [],
            "owned_projects_details": owned_details,
        }
    except Exception as exc:
        print(f"[dashboard/overview] error: {exc}")
        return {
            "total_users": 0, "projects": 0, "files": 0,
            "lines_of_code": 0, "commits": 0, "chat_messages": 0,
            "review_summary": {"total_reviews": 0, "total_issues": 0, "total_suggestions": 0},
            "most_common_issues": [], "owned_projects_details": [],
        }


@router.get("/reviews")
def review_analytics(db: Session = Depends(get_db)):
    try:
        reviews = db.query(CodeReview).all()
        return {
            "summary":       review_summary(reviews),
            "common_issues": {},
        }
    except Exception as exc:
        print(f"[dashboard/reviews] error: {exc}")
        return {"summary": {"total_reviews": 0, "total_issues": 0, "total_suggestions": 0}, "common_issues": {}}

@router.get("/review-trend")
def review_trend(project_id: int = None, db: Session = Depends(get_db)):
    """Returns { 'YYYY-MM-DD': count }. Never throws 500."""
    try:
        q = db.query(CodeReview)
        if project_id:
            q = q.filter(CodeReview.project_id == project_id)
        reviews = q.all()
        trend: dict = {}
        for r in reviews:
            if r.created_at:
                day = r.created_at.strftime("%Y-%m-%d")
                trend[day] = trend.get(day, 0) + 1
        return dict(sorted(trend.items()))
    except Exception as exc:
        print(f"[dashboard/review-trend] error: {exc}")
        return {}

@router.get("/score-trend")
def score_trend(project_id: int = None, db: Session = Depends(get_db)):
    """Returns { 'YYYY-MM-DD': avg_score }. Score is 0-100. Never throws 500."""
    try:
        q = db.query(CodeReview)
        if project_id:
            q = q.filter(CodeReview.project_id == project_id)
        reviews = q.all()
        day_scores: dict = {}
        for r in reviews:
            if r.created_at and r.score is not None:
                try:
                    s = float(r.score)
                except (TypeError, ValueError):
                    continue
                day = r.created_at.strftime("%Y-%m-%d")
                day_scores.setdefault(day, []).append(s)
        return {
            day: round(sum(scores) / len(scores), 1)
            for day, scores in sorted(day_scores.items())
        }
    except Exception as exc:
        print(f"[dashboard/score-trend] error: {exc}")
        return {}

@router.get("/files-reviewed")
def files_reviewed(db: Session = Depends(get_db)):
    try:
        count = db.query(CodeReview.file_id).distinct().count()
        return {"files_reviewed": count}
    except Exception as exc:
        print(f"[dashboard/files-reviewed] error: {exc}")
        return {"files_reviewed": 0}

@router.get("/commits")
def commit_analytics(db: Session = Depends(get_db)):
    try:
        commits = db.query(CommitHistory).all()
        stats: dict = {}
        for c in commits:
            if c.created_at:
                day = c.created_at.strftime("%Y-%m-%d")
                stats[day] = stats.get(day, 0) + 1
        return stats
    except Exception as exc:
        print(f"[dashboard/commits] error: {exc}")
        return {}

@router.get("/user-activity")
def user_activity(db: Session = Depends(get_db)):
    try:
        activities = db.query(Activity).all()
        count: dict = {}
        for a in activities:
            user = db.query(User).filter(User.id == a.user_id).first()
            key  = user.username if user else f"User #{a.user_id}"
            count[key] = count.get(key, 0) + 1
        return count
    except Exception as exc:
        print(f"[dashboard/user-activity] error: {exc}")
        return {}

@router.get("/project/{project_id}")
def project_statistics(project_id: int, db: Session = Depends(get_db)):
    try:
        files        = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
        review_count = db.query(CodeReview).filter(CodeReview.project_id == project_id).count()
        commit_count = db.query(CommitHistory).filter(CommitHistory.project_id == project_id).count()
        return {
            "project_id":    project_id,
            "files":         len(files),
            "lines_of_code": calculate_loc(files),
            "reviews":       review_count,
            "commits":       commit_count,
        }
    except Exception as exc:
        print(f"[dashboard/project] error: {exc}")
        return {"project_id": project_id, "files": 0, "lines_of_code": 0, "reviews": 0, "commits": 0}
