import argparse, io, json, sys
from .analyzer import analyze, Config, GRAPH_RULES
from .diff import git_diff, changed_lines, filter_findings
from .report import to_markdown
from . import llm

RANK = {"critical": 0, "warning": 1, "info": 2}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rosguard", description="Robotics-aware code review for ROS 2")
    ap.add_argument("command", choices=["scan", "diff"])
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--base", default="main", help="base ref for diff mode")
    ap.add_argument("--format", choices=["md", "json", "summary"], default="md")
    ap.add_argument("--fail-on", choices=["critical", "warning", "never"], default="critical")
    ap.add_argument("--llm", action="store_true", help="add AI summary (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--max-linear", type=float, default=1.5)
    ap.add_argument("--max-angular", type=float, default=2.0)
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252 and choke on emoji
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    a = ap.parse_args(argv)

    findings, _ = analyze(a.path, Config(a.max_linear, a.max_angular))
    diff_text = ""
    if a.command == "diff":
        diff_text = git_diff(a.path, a.base)
        findings = filter_findings(findings, changed_lines(diff_text), GRAPH_RULES)
    summary = llm.review(findings, diff_text) if a.llm and findings else ""
    if a.format == "summary":
        from collections import Counter
        for rule, n in sorted(Counter(f.rule for f in findings).items()):
            print(f"{rule}\t{n}")
        print(f"TOTAL\t{len(findings)}")
        return
    print(json.dumps([f.to_dict() for f in findings], indent=2) if a.format == "json"
          else to_markdown(findings, ai_summary=summary))
    if a.fail_on != "never" and any(RANK[f.severity] <= RANK[a.fail_on] for f in findings):
        sys.exit(1)


if __name__ == "__main__":
    main()
