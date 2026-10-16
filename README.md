# RosGuard — AI code review for robotics (ROS 2) MVP

Reviews pull requests for software that moves physical machines. Asks not just
"is this code good?" but "could this make the robot behave unsafely?"

## What's in the MVP
| Layer | Status |
|---|---|
| ROS 2 pub/sub graph extraction (Python + C++) | ✅ |
| Safety rules RG001–RG007, RG010 (see below) | ✅ |
| PR diff mode (only reports on changed lines) | ✅ |
| CLI + CI exit codes | ✅ |
| LLM review layer (Anthropic API, optional) | ✅ code, needs your key |
| GitHub webhook → PR comment | ✅ code, needs your token/secret |
| Simulation validation (Gazebo/Isaac) | ❌ V2 |
| GitLab, VS Code ext, dashboard, SSO | ❌ later |

## Rules
- **RG001** multiple independent `/cmd_vel` publishers (no mux/safety gate)
- **RG002** velocity publisher with no staleness/timeout/watchdog logic
- **RG003** QoS incompatibility (BEST_EFFORT publisher vs RELIABLE subscriber)
- **RG004** hard-coded velocity above limit (`--max-linear`, `--max-angular`)
- **RG005** blocking sleep in a node with callbacks
- **RG006** swallowed exceptions (`except: pass`, `catch(...) {}`)
- **RG007** unsafe default speed parameters
- **RG010** message-type mismatch between publisher and subscriber

## Use
    pip install -e .
    rosguard scan examples/bad_nav --fail-on never
    rosguard diff . --base main --llm        # PR mode
    python -m unittest discover -s tests

## GitHub
    export GITHUB_TOKEN=... GITHUB_WEBHOOK_SECRET=... ANTHROPIC_API_KEY=...
    python -m rosguard.github_app            # point a pull_request webhook at :8080
Or in CI: `rosguard diff . --base origin/main` — non-zero exit on critical findings.

## Known limits 
Rules are heuristic (regex + AST), not full semantic analysis: dynamic topic names,
remaps in launch files and namespaces are not yet resolved. Next steps: launch-file/YAML
parsing, TF-frame checks, tree-sitter for C++, then simulation-in-CI.
