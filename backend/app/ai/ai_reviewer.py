import json
import urllib.request
import urllib.error

def generate_file_review(filename: str, content: str) -> dict:
    if not content or not content.strip():
        return {
            "error": "AI Review Service Unavailable",
            "summary": "No code provided.",
            "_source": "error"
        }

    prompt = f"""
Review this single code file.

Filename:
{filename}

Code:
{content}

Analyze:

- Bugs
- Security issues
- Performance problems
- Bad practices
- Code improvements

Return detailed review.
Please format the response strictly as a JSON object (without markdown blocks) containing these keys:
"code_issue" (string), "explanation" (string), "suggested_fix" (string), "optimization" (string), "generated_documentation_comments" (string), and "overall_score" (integer 0 to 100).
"""

    url = "http://localhost:11434/api/generate"
    data = {
        "model": "qwen2.5-coder",
        "prompt": prompt,
        "stream": False,
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw = result.get("response", "").strip()
            
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            else:
                if "{" in raw and "}" in raw:
                    raw = raw[raw.find("{"):raw.rfind("}")+1]
                
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as jde:
                print(f"Ollama JSON Parse Error. Raw: {raw}")
                parsed = {"explanation": raw}
            
            if "overall_score" in parsed:
                try:
                    parsed["overall_score"] = int(parsed["overall_score"])
                except (ValueError, TypeError):
                    parsed["overall_score"] = 0
            
            parsed["_source"] = "ollama"
            return parsed
    except Exception as e:
        print(f"Ollama file review error: {e}")
        return {
            "error": "AI Review Service Unavailable",
            "_source": "error"
        }

def generate_review(code: str) -> dict:
    return generate_file_review("unknown_file", code)

