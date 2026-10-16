#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>

class Controller : public rclcpp::Node {
 public:
  Controller() : Node("controller") {
    pub_ = create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 10);
  }
  void tick() {
    geometry_msgs::msg::Twist t;
    t.angular.z = 3.0;
    try { pub_->publish(t); } catch (...) {}
  }
 private:
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr pub_;
};
