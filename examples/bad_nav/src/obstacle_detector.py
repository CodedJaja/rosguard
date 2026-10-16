import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool


class ObstacleDetector(Node):
    def __init__(self):
        super().__init__("obstacle_detector")
        self.sub = self.create_subscription(LaserScan, "/scan", self.on_scan, 10)
        qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.pub = self.create_publisher(Bool, "/obstacle", qos)

    def on_scan(self, msg):
        try:
            self.pub.publish(Bool(data=min(msg.ranges) < 0.5))
        except:
            pass
