import re, os

base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, "frontend", "js", "dashboard.js"), encoding="utf-8") as f:
    js_lines = f.readlines()

MISSING = [
    "activity-feed", "chat-messages", "chat-typing-indicator",
    "file-viewer-back-btn", "fv-comment-form", "fv-comment-input",
    "fv-comments-list", "fv-editor", "fv-save-btn", "fv-save-status",
    "rh-list", "rh-pagination", "rh-project-filter", "rh-search"
]

print("Checking guard safety for missing IDs:\n")
for mid in MISSING:
    found = [(i+1, line.rstrip()) for i, line in enumerate(js_lines) if ('el("' + mid + '")') in line or ("el('" + mid + "')") in line]
    print(f"  [{mid}]")
    for lineno, code in found:
        code_stripped = code.strip()
     
        after_el = code_stripped
        idx1 = after_el.find('el("' + mid + '")')
        idx2 = after_el.find("el('" + mid + "')")
        idx = idx1 if idx1 >= 0 else idx2
        after = after_el[idx + len('el("' + mid + '")'):]
        direct = after.startswith(".") and "if" not in after_el[:idx].lower()[-20:]
        flag = "DIRECT (risky)" if direct else "in var / guarded"
        print(f"    L{lineno}: [{flag}] {code_stripped[:110]}")
    if not found:
        print("    (not referenced)")
    print()
