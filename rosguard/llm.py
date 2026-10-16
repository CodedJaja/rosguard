"""Optional LLM layer: ranks findings and flags risks static rules miss. Stdlib only; needs ANTHROPIC_API_KEY."""
import json, os, urllib.request

SYSTEM = ("You are a senior robotics safety reviewer for ROS 2 code. Given static-analysis findings and a diff: "
          "(1) in <=120 words say which finding matters most and how it could cause unsafe physical behavior; "
          "(2) list additional risks the static rules missed (stale sensors, unbounded commands, missing e-stop/timeout, "
          "races, TF/frame errors). Be concrete; do not repeat the findings verbatim.")


def review(findings, diff_text, model=None):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return ""
    body = {"model": model or os.environ.get("ROSGUARD_MODEL", "claude-sonnet-5-5"), "max_tokens": 800, "system": SYSTEM,
            "messages": [{"role": "user", "content": "Findings:\n" + json.dumps([f.to_dict() for f in findings], indent=1)
                          + "\n\nDiff:\n" + diff_text[:30000]}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", json.dumps(body).encode(),
                                 {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return "".join(b.get("text", "") for b in json.load(r)["content"])
    except Exception as e:  # a down LLM must never fail the review
        return f"_(AI summary unavailable: {e})_"
