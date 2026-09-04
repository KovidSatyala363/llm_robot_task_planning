"""
Unit tests for the differential-drive PID controller and odometry tracker
(Parts 2 & 3 of the project).
Verifies:
  - Angle wrapping / normalization
  - Two-phase PID control: goal reached at tolerance, drive-forward otherwise
  - OdometryTracker GPS/IMU fusion and readiness flag
"""

import math
from sensor_msgs.msg import NavSatFix, Imu
from llm_robot_task_planning.controllers.pid_controller import DifferentialPIDController
from llm_robot_task_planning.controllers.odometry_tracker import OdometryTracker


def test_angle_normalization():
    assert math.isclose(DifferentialPIDController.normalize_angle(0.0), 0.0, abs_tol=1e-5)
    assert math.isclose(DifferentialPIDController.normalize_angle(3.0 * math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(DifferentialPIDController.normalize_angle(-3.0 * math.pi), -math.pi, abs_tol=1e-5)


def test_pid_controller_at_goal():
    controller = DifferentialPIDController(pos_tol=0.08, heading_tol=0.1)
    lin_vel, ang_vel, reached = controller.compute(
        current_x=1.0, current_y=1.0, current_yaw=0.0,
        target_x=1.02, target_y=1.01, target_theta=0.02
    )
    assert reached is True
    assert lin_vel == 0.0
    assert ang_vel == 0.0


def test_pid_controller_drive_forward():
    controller = DifferentialPIDController()
    lin_vel, ang_vel, reached = controller.compute(
        current_x=0.0, current_y=0.0, current_yaw=0.0,
        target_x=2.0, target_y=0.0, target_theta=0.0
    )
    assert reached is False
    assert lin_vel > 0.0  # should command forward motion toward the target


def test_pid_controller_pivots_when_misaligned():
    controller = DifferentialPIDController()
    # Target behind the robot -> pivot in place (no forward drive)
    lin_vel, ang_vel, reached = controller.compute(
        current_x=0.0, current_y=0.0, current_yaw=0.0,
        target_x=-2.0, target_y=0.0, target_theta=0.0
    )
    assert reached is False
    assert lin_vel == 0.0
    assert ang_vel > 0.0  # counterclockwise pivot toward the target heading (pi)


def test_odometry_tracker_fuses_gps_and_imu():
    odom = OdometryTracker()
    assert odom.is_ready is False

    gps = NavSatFix()
    gps.longitude = 1.23
    gps.latitude = -0.45
    odom.update_gps(gps)
    assert odom.is_ready is False  # IMU not received yet

    imu = Imu()
    imu.orientation.w = 1.0  # yaw = 0
    odom.update_imu(imu)
    assert odom.is_ready is True
    assert math.isclose(odom.pose.x, 1.23, abs_tol=1e-6)
    assert math.isclose(odom.pose.y, -0.45, abs_tol=1e-6)
    assert math.isclose(odom.pose.theta, 0.0, abs_tol=1e-6)


if __name__ == "__main__":
    import pytest
    pytest.main(["-v", __file__])
