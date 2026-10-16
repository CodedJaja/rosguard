# RosGuard

Safety-focused code review for **ROS 2** (Python and C++). RosGuard reads your code, builds a map of
which nodes publish and subscribe to what, and flags the things that can make a robot behave
unsafely: stale sensor data driving velocity commands, conflicting `/cmd_vel` publishers, QoS
mismatches, hard-coded speeds, blocking callbacks and swallowed errors. It can review a whole repo
or only the lines changed in a branch or pull request.

> **Status: early prototype.** It is rule-based and conservative. Please tell us when it is wrong.

## Quick start (about 5 minutes)

**You need:** Python 3.10 or newer, and Git (only for reviewing branches). No other packages.

### 1. Get the code
```
git clone https://github.com/CodedJaja/rosguard.git
cd rosguard
```
No Git? Use the green **Code** button on GitHub, choose **Download ZIP**, unzip it and open a terminal in the
folder that contains `pyproject.toml` and `examples/`.

### 2. Try it on the built-in demo
Nothing to install. Just run:

```
python -m rosguard.cli scan examples/bad_nav --fail-on never
```

On Windows use `python -m rosguard.cli scan examples\bad_nav --fail-on never`.
You should see a report with **10 findings** (6 critical, 3 warnings, 1 info).

### 3. Run it on your own ROS 2 repo
```
python -m rosguard.cli scan /path/to/your/repo --fail-on never
```
For a short per-rule count instead of the full report, add `--format summary`.

### 4. Review only what a branch changed (like a pull request)
```
python -m rosguard.cli diff /path/to/your/repo --base main --fail-on never
```
Use your repo's main branch name if it is not `main`. Only findings on changed lines are shown.

### Optional: install the `rosguard` command
```
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate
pip install -e .
rosguard scan examples/bad_nav --fail-on never
```

Everything runs **locally**. No code leaves your machine unless you turn on the optional AI summary.

## Reading the report

Each finding shows a rule ID, a file and line, what is wrong, and a suggested fix.

| Severity | Meaning |
|---|---|
| critical | Could directly cause unsafe or non-functional robot behaviour |
| warning | Risky pattern worth a look |
| info | Low priority, usually a code-quality note |

By default the command exits with code 1 if there are critical findings, so it can fail a CI job.
Use `--fail-on never` to always exit 0, or `--fail-on warning` to be stricter.

## Rules

| ID | What it catches |
|---|---|
| RG001 | Several independent publishers on `/cmd_vel` (teleop, example, simulation, mux and smoother nodes are ignored) |
| RG002 | A node that reads sensor input and publishes velocity with no staleness, timeout or watchdog logic |
| RG003 | QoS incompatibility: BEST_EFFORT publisher with a RELIABLE subscriber |
| RG004 | Hard-coded velocity above the limit (`--max-linear`, default 1.5 m/s; `--max-angular`, default 2.0 rad/s) |
| RG005 | Blocking sleep inside a subscription, timer or service callback |
| RG006 | Swallowed exceptions (`except: pass`, `catch (...) {}`); a warning in nodes that publish velocity, otherwise info |
| RG007 | Unsafe default value for a speed parameter |
| RG010 | Publisher and subscriber on the same topic use different message types (within one ROS package) |

Test files, `third_party`, docs and benchmark folders are skipped.

## Options

| Option | Purpose |
|---|---|
| `--format md\|json\|summary` | Report, machine-readable output, or per-rule counts |
| `--fail-on critical\|warning\|never` | When to exit non-zero |
| `--max-linear`, `--max-angular` | Your robot's real speed limits |
| `--base BRANCH` | Base branch for `diff` |
| `--llm` | Add an AI-written summary (see below) |

## Optional: AI summary

`--llm` sends the findings and the diff to the Anthropic API for a short ranked summary. It is off by
default. It needs an API key in `ANTHROPIC_API_KEY` and a funded API account.

## Check that it works

```
python -m unittest discover -s tests
python inject_bugs.py /path/to/a/ros2/repo
```

The second command copies a repo, injects known unsafe code on a branch and reports which bugs were
caught. It never modifies your repo.

## Known limits

RosGuard uses pattern matching and syntax trees, not a full ROS 2 build, so:

- Topic remaps and namespaces in launch files are not resolved yet.
- Dynamic topic names (built at runtime) are skipped.
- Callbacks are recognised from `create_subscription`, `create_timer`, `create_wall_timer` and
  `create_service`. Other patterns are missed.
- It will miss bugs that depend on timing, units or TF frames. Expect false negatives.

## Feedback

This prototype is only useful if it matches what real robot code looks like. If a finding is wrong, or
a real bug was missed, please say so. The file, line and a sentence of context is all we need.
