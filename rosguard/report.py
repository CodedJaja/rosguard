ICON = {"critical": "🔴", "warning": "🟠", "info": "🟡"}


def to_markdown(findings, title="RosGuard review", ai_summary=""):
    out = [f"## {title}", ""]
    if not findings:
        return "\n".join(out + ["✅ No robotics safety issues detected in the analyzed changes."])
    c = {s: sum(f.severity == s for f in findings) for s in ICON}
    out.append(f"**{len(findings)} issue(s)** — 🔴 {c['critical']} critical · 🟠 {c['warning']} warning · 🟡 {c['info']} info\n")
    if ai_summary:
        out += [ai_summary, ""]
    for f in findings:
        out += [f"### {ICON[f.severity]} `{f.rule}` {f.file}:{f.line}", f.message]
        if f.fix:
            out.append(f"> **Suggested fix:** {f.fix}")
        out.append("")
    return "\n".join(out)
