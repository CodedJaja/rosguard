import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class Navigator(Node):
    def __init__(self):
        super().__init__("navigator")
        self.declare_parameter("max_speed", 4.0)
        self.cmd = self.create_publisher(Twist, "/cmd_vel", 10)
        self.sub = self.create_subscription(Bool, "/obstacle", self.on_obstacle, 10)

    def on_obstacle(self, msg):
        t = Twist()
        t.linear.x = 0.0 if msg.data else 2.5
        time.sleep(0.2)
        self.cmd.publish(t)
