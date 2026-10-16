import subprocess, sys, tempfile, unittest
from pathlib import Path
from rosguard.analyzer import analyze, GRAPH_RULES
from rosguard.diff import changed_lines, filter_findings

EX = Path(__file__).parent.parent / "examples" / "bad_nav"


class T(unittest.TestCase):
    def rules(self):
        return {f.rule for f in analyze(EX)[0]}

    def test_all_rules_fire(self):
        self.assertEqual(self.rules(), {"RG001", "RG002", "RG003", "RG004", "RG005", "RG006", "RG007"})

    def test_qos_mismatch_points_at_subscriber(self):
        f = [x for x in analyze(EX)[0] if x.rule == "RG003"][0]
        self.assertEqual(f.file, "src/navigation.py")

    def test_clean_code_has_no_findings(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.py").write_text(
                "from geometry_msgs.msg import Twist\n"
                "class N:\n def __init__(s):\n  s.p = s.create_publisher(Twist, '/cmd_vel', 10)\n"
                " def cb(s, m):\n  t = Twist(); t.linear.x = 0.5\n  s.last = s.get_clock().now()\n")
            self.assertEqual(analyze(d)[0], [])

    def test_msg_type_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("class A:\n def i(s):\n  s.create_publisher(Twist, '/x', 10)\n")
            (Path(d) / "b.py").write_text("class B:\n def i(s):\n  s.create_subscription(String, '/x', s.cb, 10)\n")
            self.assertIn("RG010", {f.rule for f in analyze(d)[0]})

    def _scan(self, files):
        with tempfile.TemporaryDirectory() as d:
            for name, body in files.items():
                fp = Path(d) / name
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(body)
            return {f.rule for f in analyze(d)[0]}

    def test_keyboardinterrupt_pass_not_flagged(self):
        self.assertNotIn("RG006", self._scan({"a.py": "try:\n    spin()\nexcept KeyboardInterrupt:\n    pass\n"}))
        self.assertIn("RG006", self._scan({"a.py": "try:\n    x()\nexcept Exception:\n    pass\n"}))

    def test_rate_sleep_not_flagged(self):
        src = "class N:\n def i(s):\n  s.create_timer(1, s.cb)\n def cb(s):\n  rate.sleep()\n"
        self.assertNotIn("RG005", self._scan({"a.py": src}))

    def test_same_topic_in_different_packages_not_mismatch(self):
        r = self._scan({"p1/package.xml": "<package/>", "p1/a.py": "s.create_publisher(String, '/chatter', 10)\n",
                        "p2/package.xml": "<package/>", "p2/b.py": "s.create_subscription(Image, '/chatter', s.cb, 10)\n"})
        self.assertNotIn("RG010", r)

    def test_teleop_cmd_vel_not_conflict(self):
        pub = "from geometry_msgs.msg import Twist\nclass N:\n def i(s):\n  s.create_publisher(Twist, '/cmd_vel', 10)\n"
        self.assertNotIn("RG001", self._scan({"nav/nav.py": pub, "turtlebot3_teleop/teleop.py": pub}))
        self.assertIn("RG001", self._scan({"nav/nav.py": pub, "plan/planner.py": pub}))

    def test_test_files_skipped(self):
        self.assertEqual(self._scan({"pkg/test_thing.py": "try:\n x()\nexcept:\n pass\n"}), set())

    def test_sleep_only_flagged_inside_callbacks_py(self):
        helper = "import time\nclass N:\n def i(s):\n  s.create_subscription(M, '/a', s.cb, 10)\n def cb(s, m):\n  pass\n def wait(s):\n  time.sleep(2)\ndef main():\n  time.sleep(1)\n"
        self.assertNotIn("RG005", self._scan({"a.py": helper}))
        bad = helper.replace("def cb(s, m):\n  pass", "def cb(s, m):\n  time.sleep(1)")
        self.assertIn("RG005", self._scan({"a.py": bad}))

    def test_sleep_only_flagged_inside_callbacks_cpp(self):
        base = ('#include <thread>\nclass N { N() { sub_ = create_subscription<M>("/a", 10, std::bind(&N::cb, this, _1)); }\n'
                ' void cb(const M & m) { %s }\n};\nint main() { std::this_thread::sleep_for(200ms); }\n')
        self.assertNotIn("RG005", self._scan({"a.cpp": base % "int x = 1;"}))
        self.assertIn("RG005", self._scan({"a.cpp": base % "std::this_thread::sleep_for(100ms);"}))
        lam = 'void f() { sub_ = create_subscription<M>("/a", 10, [this](const M & m) { std::this_thread::sleep_for(1s); }); }\n'
        self.assertIn("RG005", self._scan({"b.cpp": lam}))

    def test_array_index_and_deadband_not_velocity(self):
        src = "void f() {\n  cmd->twist.angular.z = fabs(cmd->twist.angular.z) < deadband_[5] ? 0.0 : cmd->twist.angular.z;\n}\n"
        self.assertNotIn("RG004", self._scan({"a.cpp": src}))
        self.assertIn("RG004", self._scan({"b.py": "t.linear.x = 0.0 if stop else 2.5\n"}))

    def test_swallowed_is_info_without_cmd_vel(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.cpp").write_text("void f() { try { g(); } catch (...) {} }\n")
            (Path(d) / "b.py").write_text("from geometry_msgs.msg import Twist\nclass N:\n def i(s):\n  s.create_publisher(Twist, '/cmd_vel', 10)\n def f(s):\n  try:\n   g()\n  except Exception:\n   pass\n")
            sev = {f.file: f.severity for f in analyze(d)[0] if f.rule == "RG006"}
        self.assertEqual(sev, {"a.cpp": "info", "b.py": "warning"})

    def test_diff_filter(self):
        diff = "+++ b/src/navigation.py\n@@ -14,0 +14,6 @@\n+x\n+y\n"
        kept = filter_findings(analyze(EX)[0], changed_lines(diff), GRAPH_RULES)
        self.assertTrue(kept and all(f.file == "src/navigation.py" for f in kept))
        self.assertTrue(any(f.rule == "RG004" for f in kept))


if __name__ == "__main__":
    unittest.main()
