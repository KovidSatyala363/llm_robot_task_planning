import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix, Imu
from std_msgs.msg import String
import json
import time
import math
from llm_robot_task_planning.skills.skill_interface import SkillResult

class NavigationNode(Node):
    def __init__(self):
        super().__init__('navigation_node')

        self.cmd_vel_pub = self.create_publisher(Twist, '/agent0/cmd_vel', 10)
        self.result_pub = self.create_publisher(String, '/agent0/skill_result', 10)

        self.skill_sub = self.create_subscription(String, '/agent0/execute_skill', self.execute_skill_callback, 10)
        self.gps_sub = self.create_subscription(NavSatFix, '/agent0/gps', self.gps_callback, 10)
        self.imu_sub = self.create_subscription(Imu, '/agent0/inertial_unit', self.imu_callback, 10)

        # Robot pose in ENU frame
        self.current_x = 0.0
        self.current_y = -1.7
        self.current_yaw = 1.5708

        self.is_navigating = False
        self.target_x = 0.0
        self.target_y = 0.0
        self.target_theta = 0.0
        self.nav_start_time = 0.0
        self.timeout_s = 35.0          # per leg / waypoint
        self.ALIGN_GRACE_S = 8.0       # max time rotating to final heading
        self.alignment_start_time = None
        self.current_skill_name = ""

        # follow_waypoints state
        self.waypoints_queue = []
        self.follow_waypoints_start_time = 0.0
        self.original_waypoints_count = 0
        self.current_waypoint_idx = 0          # waypoint being driven to
        self.last_reached_waypoint_idx = None  # last waypoint fully reached

        # 20 Hz control loop
        self.control_timer = self.create_timer(0.05, self.control_loop)
        self.get_logger().info("Navigation Node active with smooth Pure-Pursuit controller.")

    def gps_callback(self, msg: NavSatFix):
        self.current_x = float(msg.longitude)
        self.current_y = float(msg.latitude)

    def imu_callback(self, msg: Imu):
        q = msg.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def normalize_angle(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def execute_skill_callback(self, msg: String):
        data = json.loads(msg.data)
        skill = data.get("skill")
        args = data.get("arguments", {})

        self.get_logger().info(f"Executing: {skill} {args}")

        if skill == "navigate_to":
            self.start_navigate_to(args['x'], args['y'], args.get('theta', 0.0), skill_name="navigate_to")
        elif skill == "follow_waypoints":
            waypoints = list(args.get('waypoints', []))
            if not waypoints:
                self.publish_result(SkillResult(
                    skill="follow_waypoints",
                    success=False,
                    reason="empty_waypoints",
                    position_error_m=0.0,
                    elapsed_time_s=0.0
                ))
                return
            self.waypoints_queue = waypoints
            self.original_waypoints_count = len(waypoints)
            self.follow_waypoints_start_time = time.time()
            self.current_waypoint_idx = 0
            self.last_reached_waypoint_idx = None
            first_wp = self.waypoints_queue.pop(0)
            self.start_navigate_to(first_wp['x'], first_wp['y'], first_wp.get('theta', 0.0), skill_name="follow_waypoints")
        elif skill == "stop":
            self.is_navigating = False
            self.cmd_vel_pub.publish(Twist())
            self.publish_result(SkillResult(
                skill="stop",
                success=True,
                reason="stopped",
                position_error_m=0.0,
                elapsed_time_s=0.0
            ))
        else:
            self.publish_result(SkillResult(
                skill=skill,
                success=False,
                reason="Unknown skill",
                position_error_m=0.0,
                elapsed_time_s=0.0
            ))

    def start_navigate_to(self, tx: float, ty: float, t_theta: float, skill_name: str = "navigate_to"):
        self.target_x = float(tx)
        self.target_y = float(ty)
        self.target_theta = float(t_theta)
        self.current_skill_name = skill_name
        self.nav_start_time = time.time()
        self.alignment_start_time = None
        self.is_navigating = True

    def control_loop(self):
        if not self.is_navigating:
            return

        elapsed = time.time() - self.nav_start_time

        if elapsed > self.timeout_s:
            self.is_navigating = False
            self.cmd_vel_pub.publish(Twist())
            err = math.hypot(self.target_x - self.current_x, self.target_y - self.current_y)

            # follow_waypoints: abort remaining queue and report failure
            if self.current_skill_name == "follow_waypoints":
                self.waypoints_queue.clear()
                self.publish_result(SkillResult(
                    skill="follow_waypoints",
                    success=False,
                    reason=f"timeout at waypoint {self.current_waypoint_idx}",
                    position_error_m=round(err, 3),
                    elapsed_time_s=round(time.time() - self.follow_waypoints_start_time, 2),
                    waypoint_reached_idx=self.last_reached_waypoint_idx
                ))
            else:
                self.publish_result(SkillResult(
                    skill=self.current_skill_name,
                    success=False,
                    reason="timeout",
                    position_error_m=round(err, 3),
                    elapsed_time_s=round(elapsed, 2)
                ))
            return

        dx = self.target_x - self.current_x
        dy = self.target_y - self.current_y
        dist_err = math.hypot(dx, dy)

        POSITION_TOLERANCE = 0.25  # 25 cm
        HEADING_TOLERANCE = 0.35   # ~20 deg

        twist = Twist()

        # Drive to target position
        if dist_err > POSITION_TOLERANCE:
            self.alignment_start_time = None
            target_head = math.atan2(dy, dx)
            head_err = self.normalize_angle(target_head - self.current_yaw)

            if abs(head_err) > 0.60:
                twist.linear.x = 0.0
                twist.angular.z = max(min(2.5 * head_err, 1.8), -1.8)
            else:
                twist.linear.x = max(min(1.2 * dist_err, 0.55), 0.25)
                twist.angular.z = 2.0 * head_err
            self.cmd_vel_pub.publish(twist)
        else:
            # Align final heading (position already reached)
            if self.alignment_start_time is None:
                self.alignment_start_time = time.time()
            align_elapsed = time.time() - self.alignment_start_time

            final_head_err = self.normalize_angle(self.target_theta - self.current_yaw)
            heading_ok = abs(final_head_err) <= HEADING_TOLERANCE

            if not heading_ok and align_elapsed < self.ALIGN_GRACE_S:
                twist.linear.x = 0.0
                twist.angular.z = max(min(2.0 * final_head_err, 1.5), -1.5)
                self.cmd_vel_pub.publish(twist)
            else:
                # Goal reached (heading aligned or grace time expired)
                self.cmd_vel_pub.publish(Twist())

                # More waypoints queued: advance to the next one
                if self.current_skill_name == "follow_waypoints" and self.waypoints_queue:
                    self.last_reached_waypoint_idx = self.current_waypoint_idx
                    self.current_waypoint_idx += 1
                    next_wp = self.waypoints_queue.pop(0)
                    self.start_navigate_to(
                        next_wp['x'],
                        next_wp['y'],
                        next_wp.get('theta', 0.0),
                        skill_name="follow_waypoints"
                    )
                else:
                    self.is_navigating = False
                    if self.current_skill_name == "follow_waypoints":
                        elapsed_total = time.time() - self.follow_waypoints_start_time
                        self.publish_result(SkillResult(
                            skill="follow_waypoints",
                            success=True,
                            reason="arrived",
                            position_error_m=round(dist_err, 3),
                            elapsed_time_s=round(elapsed_total, 2),
                            waypoint_reached_idx=self.original_waypoints_count - 1
                        ))
                    else:
                        self.publish_result(SkillResult(
                            skill=self.current_skill_name,
                            success=True,
                            reason="arrived",
                            position_error_m=round(dist_err, 3),
                            elapsed_time_s=round(elapsed, 2)
                        ))

    def publish_result(self, result: SkillResult):
        self.result_pub.publish(String(data=json.dumps(result.model_dump())))

def main(args=None):
    rclpy.init(args=args)
    node = NavigationNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
