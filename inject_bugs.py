"""Recall test: copy a real ROS 2 repo, inject known-unsafe code on a branch, run `rosguard diff`,
and report which injected bugs were caught.   Usage:  python inject_bugs.py [path-to-repo]"""
import io, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "ros-targets" / "turtlebot3"
PKG = "turtlebot3_injected_bugs"

FILES = {
"package.xml": "<package><name>turtlebot3_injected_bugs</name></package>\n",
"stale_driver.py": '''from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class StaleDriver(Node):
    def __init__(self):
        super().__init__('stale_driver')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(LaserScan, '/scan', self.on_scan, 10)

    def on_scan(self, msg):
        t = Twist()
        t.linear.x = 0.2 if min(msg.ranges) > 0.5 else 0.0
        self.cmd_pub.publish(t)
''',
"rogue_planner.py": '''import time
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class RoguePlanner(Node):
    def __init__(self):
        super().__init__('rogue_planner')
        self.declare_parameter('max_speed', 5.0)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Bool, '/go', self.on_go, 10)

    def on_go(self, msg):
        t = Twist()
        t.linear.x = 2.5
        time.sleep(0.5)
        try:
            self.cmd_pub.publish(t)
        except Exception:
            pass
''',
"qos_pair.py": '''from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


class Detector(Node):
    def __init__(self):
        super().__init__('detector')
        qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.pub = self.create_publisher(Bool, '/obstacle', qos)


class Consumer(Node):
    def __init__(self):
        super().__init__('consumer')
        self.sub = self.create_subscription(Bool, '/obstacle', self.cb, 10)

    def cb(self, msg):
        pass
''',
"type_mismatch.py": '''from rclpy.node import Node
from std_msgs.msg import String, Int32


class A(Node):
    def __init__(self):
        super().__init__('a')
        self.pub = self.create_publisher(String, '/status', 10)


class B(Node):
    def __init__(self):
        super().__init__('b')
        self.sub = self.create_subscription(Int32, '/status', self.cb, 10)

    def cb(self, msg):
        pass
''',
}
EXPECTED = {
    "RG001": "second independent /cmd_vel publisher",
    "RG002": "velocity from sensor data with no staleness check",
    "RG003": "BEST_EFFORT publisher vs RELIABLE subscriber",
    "RG004": "hard-coded velocity 2.5 m/s",
    "RG005": "time.sleep() inside a subscription callback",
    "RG006": "swallowed exception around a velocity publish",
    "RG007": "unsafe default max_speed = 5.0",
    "RG010": "message type mismatch (String vs Int32)",
}


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def main():
    if not SRC.exists():
        sys.exit(f"Repo not found: {SRC}")
    work = Path(tempfile.mkdtemp(prefix="rosguard_inject_")) / "repo"
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns(".git"))
    git(work, "init", "-q", "-b", "main"); git(work, "add", "-A"); git(work, "commit", "-q", "-m", "base")
    git(work, "checkout", "-q", "-b", "feature")
    (work / PKG).mkdir()
    for name, body in FILES.items():
        (work / PKG / name).write_text(body, encoding="utf-8")
    git(work, "add", "-A"); git(work, "commit", "-q", "-m", "inject bugs")

    r = subprocess.run([sys.executable, "-m", "rosguard.cli", "diff", str(work), "--base", "main",
                        "--format", "json", "--fail-on", "never"],
                       cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit("rosguard failed:\n" + r.stderr)
    found = json.loads(r.stdout)
    got = {f["rule"] for f in found}
    print(f"\nSource repo : {SRC}\nWorkspace   : {work}\n")
    print(f"{'Rule':<7}{'Result':<8}Injected bug")
    for rule, what in EXPECTED.items():
        print(f"{rule:<7}{'CAUGHT' if rule in got else 'MISSED':<8}{what}")
    caught = sum(r_ in got for r_ in EXPECTED)
    extra = [f for f in found if f["rule"] not in EXPECTED]
    print(f"\nRecall: {caught}/{len(EXPECTED)} injected bug classes caught; {len(found)} findings total.")
    outside = [f for f in found if not f["file"].startswith(PKG)]
    print(f"Findings outside the injected files: {len(outside)} (should be 0)")
    for f in outside + extra:
        print(f"  {f['rule']} {f['file']}:{f['line']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
