"""GitHub webhook server: on PR open/update, clone, run diff review, post a PR comment.
Env: GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, optional ANTHROPIC_API_KEY, PORT."""
import hashlib, hmac, json, os, subprocess, tempfile, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from .analyzer import analyze, GRAPH_RULES
from .diff import git_diff, changed_lines, filter_findings
from .report import to_markdown
from . import llm

TOKEN, SECRET = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def post_comment(repo, number, body):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{number}/comments",
                                 json.dumps({"body": body}).encode(),
                                 {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    urllib.request.urlopen(req, timeout=30)


def review_pr(payload):
    pr, repo = payload["pull_request"], payload["repository"]["full_name"]
    with tempfile.TemporaryDirectory() as d:
        run = lambda *c: subprocess.run(["git", "-C", d, *c], check=True)
        subprocess.run(["git", "clone", "--quiet", f"https://x-access-token:{TOKEN}@github.com/{repo}.git", d], check=True)
        run("fetch", "--quiet", "origin", f"pull/{pr['number']}/head:pr")
        run("checkout", "--quiet", "pr")
        findings, _ = analyze(d)
        diff = git_diff(d, f"origin/{pr['base']['ref']}")
        findings = filter_findings(findings, changed_lines(diff), GRAPH_RULES)
        post_comment(repo, pr["number"], to_markdown(findings, ai_summary=llm.review(findings, diff) if findings else ""))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length", 0)))
        sig = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, self.headers.get("x-hub-signature-256", "")):
            self.send_response(401); self.end_headers(); return
        p = json.loads(raw)
        if self.headers.get("x-github-event") == "pull_request" and p.get("action") in ("opened", "synchronize", "reopened"):
            try:
                review_pr(p)
            except Exception as e:
                print("review failed:", e)
        self.send_response(200); self.end_headers()


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), Handler).serve_forever()
