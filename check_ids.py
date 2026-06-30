import re, os, sys

base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, "frontend", "js", "dashboard.js"), encoding="utf-8") as f:
    js = f.read()

with open(os.path.join(base, "frontend", "index.html"), encoding="utf-8") as f:
    html = f.read()

js_ids = set(re.findall(r'el\("([^"]+)"\)', js))
js_ids |= set(re.findall(r"el\('([^']+)'\)", js))

html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

missing = sorted(js_ids - html_ids)
print("IDs in JS missing from HTML:")
for m in missing:
    print("  MISSING:", m)
print(f"\nTotal missing: {len(missing)}")
print("\nPresent in both (ok):", len(js_ids & html_ids))
