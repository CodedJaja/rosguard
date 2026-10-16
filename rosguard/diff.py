"""Map a git diff to changed line numbers so PR review only reports on what the PR touched."""
import re, subprocess


def git_diff(repo, base):
    return subprocess.run(["git", "-C", str(repo), "diff", "-U0", f"{base}...HEAD"],
                          capture_output=True, text=True, check=True).stdout


def changed_lines(diff_text):
    out, cur = {}, None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]; out.setdefault(cur, set())
        elif line.startswith("@@") and cur:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start, n = int(m.group(1)), int(m.group(2) or 1)
            out[cur].update(range(start, start + n))
    return out


def filter_findings(findings, changed, graph_rules):
    keep = []
    for f in findings:
        lines = next((v for k, v in changed.items() if k.endswith(f.file)), None)
        if lines is not None and (f.rule in graph_rules or f.line in lines):
            keep.append(f)
    return keep
