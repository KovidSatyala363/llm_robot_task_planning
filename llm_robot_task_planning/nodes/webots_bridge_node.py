import sys
import os

# Locate Webots Python API
webots_paths = [
    os.environ.get('WEBOTS_HOME', '') + '/lib/controller/python',
    '/usr/local/webots/lib/controller/python',
    '/usr/share/webots/lib/controller/python',
    '/snap/webots/current/usr/share/webots/lib/controller/python',
    '/app/webots/lib/controller/python'
]
for p in webots_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

try:
    from controller import Robot
except ImportError:
    print("[ERROR] Webots Python API not found.")
    sys.exit(1)

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix, Imu
import math

class WebotsRobotBridge(Node):
    def __init__(self):
        super().__init__('webots_bridge_node')
        os.environ['WEBOTS_ROBOT_NAME'] = 'agent0'
        self.robot = Robot()
        self.time_step = int(self.robot.getBasicTimeStep())

        # Motors
        self.left_motor = self.robot.getDevice('left wheel motor')
        self.right_motor = self.robot.getDevice('right wheel motor')
        self.left_motor.setPosition(float('inf'))
        self.right_motor.setPosition(float('inf'))
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

        self.wheel_radius = 0.045
        self.track_width = 0.24

        # Sensors
        self.gps = self.robot.getDevice('gps')
        if self.gps:
            self.gps.enable(self.time_step)

        self.imu = self.robot.getDevice('inertial_unit')
        if self.imu:
            self.imu.enable(self.time_step)

        # ROS 2 Topics
        self.gps_pub = self.create_publisher(NavSatFix, '/agent0/gps', 10)
        self.imu_pub = self.create_publisher(Imu, '/agent0/inertial_unit', 10)
        self.cmd_sub = self.create_subscription(Twist, '/agent0/cmd_vel', self.cmd_vel_cb, 10)

        self.target_left_speed = 0.0
        self.target_right_speed = 0.0
        self.get_logger().info("Webots Robot Bridge successfully connected to 'agent0'.")

    def cmd_vel_cb(self, msg: Twist):
        lin = msg.linear.x
        ang = msg.angular.z
        self.target_left_speed = (lin - (ang * self.track_width / 2.0)) / self.wheel_radius
        self.target_right_speed = (lin + (ang * self.track_width / 2.0)) / self.wheel_radius
        self.target_left_speed = max(min(self.target_left_speed, 15.0), -15.0)
        self.target_right_speed = max(min(self.target_right_speed, 15.0), -15.0)

    def publish_sensors(self):
        if self.gps:
            vals = self.gps.getValues()
            msg = NavSatFix()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'agent0_link'
            msg.longitude = float(vals[0]) # ENU X
            msg.latitude = float(vals[1])  # ENU Y
            msg.altitude = float(vals[2])  # ENU Z
            self.gps_pub.publish(msg)

        if self.imu:
            rpy = self.imu.getRollPitchYaw()
            yaw = rpy[2] # ENU Yaw
            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = 'agent0_link'
            msg.orientation.z = math.sin(yaw / 2.0)
            msg.orientation.w = math.cos(yaw / 2.0)
            self.imu_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    bridge = WebotsRobotBridge()

    # Webots simulation step loop
    while rclpy.ok() and bridge.robot.step(bridge.time_step) != -1:
        rclpy.spin_once(bridge, timeout_sec=0.0)
        bridge.left_motor.setVelocity(bridge.target_left_speed)
        bridge.right_motor.setVelocity(bridge.target_right_speed)
        bridge.publish_sensors()

    bridge.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
