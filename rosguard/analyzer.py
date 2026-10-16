"""ROS 2 static analysis: builds a pub/sub graph from Python + C++ and runs robotics safety rules."""
from __future__ import annotations
import ast, re
from dataclasses import dataclass, asdict
from pathlib import Path

EXTS = {".py": "py", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".h": "cpp"}
SKIP = {".git", "build", "install", "log", "node_modules", "tests", "test", "__pycache__", "venv", ".venv", "third_party", "3rdparty", "docs", "doc", "benchmark", "benchmarks"}
TESTFILE = re.compile(r"(^test_|_test\.|_tests?$|system_tests?$|^tests?$)", re.I)
GRAPH_RULES = {"RG001", "RG003", "RG010"}


@dataclass
class Finding:
    rule: str
    severity: str  # critical | warning | info
    file: str
    line: int
    message: str
    fix: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Endpoint:
    kind: str  # pub | sub
    topic: str
    msg: str
    qos: str
    file: str
    line: int
    pkg: str = ""


@dataclass
class Config:
    max_linear: float = 1.5   # m/s
    max_angular: float = 2.0  # rad/s


def qos_kind(text: str) -> str:
    if re.search(r"BEST_EFFORT|sensor_data|SensorDataQoS|best_effort\(\)", text or ""):
        return "best_effort"
    return "reliable"


def short_msg(m: str) -> str:
    return re.split(r"[.:/]+", m.strip())[-1]


def package_of(p: Path, base: Path) -> str:
    """Nearest ancestor directory containing package.xml (ROS package), else top-level dir."""
    for d in [p.parent, *p.parent.parents]:
        if (d / "package.xml").exists():
            return d.relative_to(base).as_posix()
        if d == base:
            break
    return p.relative_to(base).parts[0] if len(p.relative_to(base).parts) > 1 else "."


def _skipped(parts) -> bool:
    *dirs, name = parts
    return bool(SKIP & set(dirs)) or any(TESTFILE.search(d) for d in dirs) or bool(TESTFILE.search(name.rsplit(".", 1)[0]))


def discover(root: Path):
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob("*"))
    for p in files:
        parts = (p.name,) if root.is_file() else p.relative_to(root).parts
        if p.suffix in EXTS and not _skipped(parts):
            yield p, EXTS[p.suffix]


def _py_endpoints(tree, rel):
    raw, names = [], {}
    for n in ast.walk(tree):  # resolve `qos = QoSProfile(...)` style variables
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            key = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else None)
            if key:
                names[key] = ast.unparse(n.value)
    def res(node):
        txt = ast.unparse(node)
        return txt + " " + names.get(txt.split(".")[-1], "") if isinstance(node, (ast.Name, ast.Attribute)) else txt
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        a, args = n.func.attr, n.args
        kw = {k.arg: ast.unparse(k.value) for k in n.keywords}
        if a == "create_publisher" and len(args) >= 2:
            qos = res(args[2]) if len(args) > 2 else kw.get("qos_profile", "10")
            raw.append(("pub", args[1], args[0], qos, n.lineno))
        elif a == "create_subscription" and len(args) >= 3:
            qos = res(args[3]) if len(args) > 3 else kw.get("qos_profile", "10")
            raw.append(("sub", args[1], args[0], qos, n.lineno))
    return [Endpoint(k, t.value.lstrip("/"), ast.unparse(m), qos_kind(q), rel, ln)
            for k, t, m, q, ln in raw if isinstance(t, ast.Constant) and isinstance(t.value, str)]


CPP_EP = re.compile(r'create_(publisher|subscription)\s*<\s*([^>]+?)\s*>\s*\(\s*"([^"]+)"\s*,\s*([^;]*);')


def _cpp_endpoints(text, rel):
    return [Endpoint("pub" if m.group(1) == "publisher" else "sub", m.group(3).lstrip("/"), m.group(2),
                     qos_kind(m.group(4)), rel, text.count("\n", 0, m.start()) + 1)
            for m in CPP_EP.finditer(text)]


VEL = re.compile(r"(linear\.[xy]|angular\.z)[ \t]*=[ \t]*([^\n;=][^\n;]*)")
PARAM = re.compile(r"declare_parameter(?:<[^>]*>)?\(\s*[\"']([^\"']*(?:vel|speed)[^\"']*)[\"']\s*,\s*(-?\d+(?:\.\d+)?)", re.I)
SLEEP = re.compile(r"\btime\.sleep\(|std::this_thread::sleep_for|\busleep\(|(?<![.\w>:])sleep\(")
CPP_SWALLOW = re.compile(r"catch\s*\(\s*\.\.\.\s*\)\s*\{\s*\}")
FRESH = re.compile(r"stamp|\.now\(\)|timeout|watchdog|deadline", re.I)
EXAMPLEISH = re.compile(r"(^|[/_.-])(example|examples|demo|demos|sample|samples|tutorial)([/_.-]|$)", re.I)
CB_CALL = re.compile(r"create_(?:subscription|wall_timer|timer|service)\b")
CB_REF = re.compile(r"&\s*\w+::(\w+)")
LAMBDA = re.compile(r"\[[^\]]*\]\s*\([^)]*\)\s*(?:mutable\s*)?(?:->\s*[\w:<>]+\s*)?\{")


def _ln(text, pos):
    return text.count("\n", 0, pos) + 1


def _brace_body(text, i):
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return i, j
    return i, len(text)


def _cpp_callback_ranges(text):
    """Source ranges of C++ subscription/timer/service callbacks (lambdas and named methods)."""
    ranges, names = [], set()
    for m in CB_CALL.finditer(text):
        win = text[m.start(): m.start() + 1500]
        names.update(CB_REF.findall(win.split(";")[0]))
        lm = LAMBDA.search(win)
        if lm:
            ranges.append(_brace_body(text, m.start() + lm.end() - 1))
    for n in names:
        for dm in re.finditer(r"\b(?:\w+::)?" + re.escape(n) + r"\s*\([^;{)]*\)[^;{]*\{", text):
            ranges.append(_brace_body(text, dm.end() - 1))
    return ranges


def _py_callback_sleeps(text):
    """Line numbers of time.sleep() calls inside functions registered as subscription/timer/service callbacks."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    names, pos = set(), {"create_subscription": 2, "create_timer": 1, "create_service": 2}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in pos:
            i = pos[n.func.attr]
            arg = n.args[i] if len(n.args) > i else next((k.value for k in n.keywords if k.arg == "callback"), None)
            if isinstance(arg, ast.Attribute):
                names.add(arg.attr)
            elif isinstance(arg, ast.Name):
                names.add(arg.id)
    out = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name in names:
            for c in ast.walk(fn):
                if isinstance(c, ast.Call) and (
                        (isinstance(c.func, ast.Attribute) and c.func.attr == "sleep"
                         and isinstance(c.func.value, ast.Name) and c.func.value.id == "time")
                        or (isinstance(c.func, ast.Name) and c.func.id == "sleep")):
                    out.append(c.lineno)
    return out


def _velocity_numbers(rhs):
    rhs = re.sub(r"\[[^\]]*\]", "", rhs)  # drop array indices like deadband_[5]
    rhs = re.sub(r"[<>]=?\s*-?\d+(?:\.\d+)?|-?\d+(?:\.\d+)?\s*[<>]=?", "", rhs)  # drop comparison thresholds
    return [abs(float(x)) for x in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", rhs)]


def _file_rules(rel, text, lang, eps, cfg):
    f = []
    cmd_pubs = [e for e in eps if e.kind == "pub" and e.topic.endswith("cmd_vel")]
    for m in VEL.finditer(text):  # RG004
        field = m.group(1)
        nums = _velocity_numbers(m.group(2))
        lim = cfg.max_angular if field.startswith("angular") else cfg.max_linear
        if nums and max(nums) > lim:
            f.append(Finding("RG004", "critical", rel, _ln(text, m.start()),
                             f"Hard-coded velocity command {field} up to {max(nums)} exceeds the configured limit ({lim}).",
                             "Clamp commands through a shared velocity limiter (e.g. nav2_velocity_smoother) instead of literals."))
    for m in PARAM.finditer(text):  # RG007
        if abs(float(m.group(2))) > cfg.max_linear:
            f.append(Finding("RG007", "warning", rel, _ln(text, m.start()),
                             f"Parameter '{m.group(1)}' defaults to {m.group(2)}, above the {cfg.max_linear} m/s safe default.",
                             "Default to a conservative value and require explicit override in launch/config files."))
    if cmd_pubs and any(e.kind == "sub" for e in eps) and not FRESH.search(text):  # RG002
        f.append(Finding("RG002", "warning" if EXAMPLEISH.search(rel) else "critical", rel, cmd_pubs[0].line,
                         "Node consumes sensor input and publishes velocity commands with no staleness, timeout or watchdog logic.",
                         "Track the last sensor stamp and publish zero velocity when data is older than a deadline."))
    # RG005: only sleeps inside subscription/timer/service callbacks (main loops and helpers are fine)
    if lang == "py":
        sleeps = _py_callback_sleeps(text)
    else:
        sleeps = sorted({_ln(text, m.start()) for a, b in _cpp_callback_ranges(text) for m in SLEEP.finditer(text, a, b)})
    for ln in sleeps:
        f.append(Finding("RG005", "warning", rel, ln,
                         "Blocking sleep inside a subscription/timer/service callback stalls the executor and delays control/sensor handling.",
                         "Use a timer (create_timer) or rate object instead of sleeping."))
    # RG006: swallowed errors matter most where velocity commands are produced
    sev = "warning" if cmd_pubs else "info"
    if lang == "py":
        try:
            for n in ast.walk(ast.parse(text)):
                if (isinstance(n, ast.ExceptHandler) and all(isinstance(b, (ast.Pass, ast.Continue)) for b in n.body)
                        and (n.type is None or ast.unparse(n.type) in ("Exception", "BaseException"))):
                    f.append(Finding("RG006", sev, rel, n.lineno,
                                     "Exception swallowed silently; a failed sensor/actuator call goes unnoticed.",
                                     "Log the error and fall back to a safe state (stop the robot)."))
        except SyntaxError:
            pass
    else:
        for m in CPP_SWALLOW.finditer(text):
            f.append(Finding("RG006", sev, rel, _ln(text, m.start()),
                             "catch(...) with empty body swallows errors silently.",
                             "Log and transition to a safe state."))
    return f


BENIGN_MULTI_PUB = re.compile(r"(^|[/_.-])(teleop|teleoperation|example|examples|demo|demos|sample|samples|gazebo|sim|simulation|mux|smoother|safety|monitor)([/_.-]|$)", re.I)


def _graph_rules(eps):
    f = []
    # RG001: repo-wide, but ignore teleop/example/sim/mux nodes (legitimate alternative sources)
    cmd = [e for e in eps if e.kind == "pub" and e.topic.endswith("cmd_vel") and not BENIGN_MULTI_PUB.search(e.file)]
    files = {e.file for e in cmd}
    if len(files) > 1:
        for p in cmd:
            f.append(Finding("RG001", "critical", p.file, p.line,
                             f"/cmd_vel has {len(files)} independent publishers (also: {', '.join(sorted(files - {p.file}))}); commands can conflict.",
                             "Route all sources through a twist_mux / safety gate so one node owns the final command."))
    # Pub/sub compatibility is only meaningful within one ROS package
    by = {}
    for e in eps:
        by.setdefault((e.pkg, e.topic), []).append(e)
    for (pkg, topic), es in by.items():
        pubs, subs = [e for e in es if e.kind == "pub"], [e for e in es if e.kind == "sub"]
        if not pubs or not subs:
            continue
        if all(p.qos == "best_effort" for p in pubs):  # RG003
            for s_ in (x for x in subs if x.qos == "reliable"):
                p = pubs[0]
                f.append(Finding("RG003", "critical", s_.file, s_.line,
                                 f"QoS incompatible on /{topic}: publisher ({p.file}:{p.line}) is BEST_EFFORT but subscriber requests RELIABLE; no messages will be delivered.",
                                 "Use SensorDataQoS / BEST_EFFORT on the subscriber, or make the publisher RELIABLE."))
        pt, st = {short_msg(p.msg) for p in pubs}, {short_msg(x.msg) for x in subs}
        if not (pt & st):  # RG010: no publisher/subscriber type overlap at all
            f.append(Finding("RG010", "warning", subs[0].file, subs[0].line,
                             f"Message type mismatch on /{topic}: publishers use {sorted(pt)}, subscribers use {sorted(st)}.",
                             "Align message types across both nodes."))
    return f


def analyze(root, cfg: Config | None = None):
    cfg, root = cfg or Config(), Path(root)
    base = root if root.is_dir() else root.parent
    eps, findings = [], []
    for p, lang in discover(root):
        text, rel = p.read_text(errors="ignore"), p.relative_to(base).as_posix()
        if lang == "py":
            try:
                fe = _py_endpoints(ast.parse(text), rel)
            except SyntaxError:
                fe = []
        else:
            fe = _cpp_endpoints(text, rel)
        pkg = package_of(p, base)
        for e in fe:
            e.pkg = pkg
        eps += fe
        findings += _file_rules(rel, text, lang, fe, cfg)
    findings += _graph_rules(eps)
    order, seen, uniq = {"critical": 0, "warning": 1, "info": 2}, set(), []
    for x in sorted(findings, key=lambda x: (order[x.severity], x.file, x.line)):
        k = (x.rule, x.file, x.line, x.message)
        if k not in seen:
            seen.add(k); uniq.append(x)
    return uniq, eps
