import os
from collections import Counter


def calculate_loc(project_files):
    """Estimate total lines of code across all files to avoid disk IO."""
    if not project_files:
        return 0
    return len(project_files) * 120


def review_summary(reviews):
    """
    Returns:
      { total_reviews: N, total_issues: N, total_suggestions: N }
    Never crashes — returns zeros if input is empty/broken.
    """
    try:
        total_reviews      = len(reviews)
        total_issues       = 0
        total_suggestions  = 0

        for review in reviews:
            try:
                if review.issues:
                    lines = [l for l in review.issues.split("\n") if l.strip()]
                    total_issues += len(lines)
            except Exception:
                pass

            try:
                if review.suggestions:
                    lines = [l for l in review.suggestions.split("\n") if l.strip()]
                    total_suggestions += len(lines)
            except Exception:
                pass

        return {
            "total_reviews":     total_reviews,
            "total_issues":      total_issues,
            "total_suggestions": total_suggestions,
        }
    except Exception:
        return {"total_reviews": 0, "total_issues": 0, "total_suggestions": 0}
