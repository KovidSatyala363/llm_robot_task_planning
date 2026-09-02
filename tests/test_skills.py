"""
Unit Tests for PID Controller and Navigation Skills (Part 2 & Part 3)
Verifies:
  - PID control output calculation and angle wrapping
  - navigate_to reaching goal within tolerance
  - navigate_to timeout handling
  - follow_waypoints sequential execution and last_reached_index tracking
  - stop skill behavior
"""

import math
import pytest
from llm_robot_task_planning.controllers.pid_controller import PIDPoseController, wrap_angle
from llm_robot_task_planning.controllers.odometry_tracker import OdometryTracker
from llm_robot_task_planning.skills.navigation_skills import NavigationSkills
from llm_robot_task_planning.skills.skill_interface import Waypoint, SkillResult


def test_angle_wrapping():
    assert math.isclose(wrap_angle(0.0), 0.0, abs_tol=1e-5)
    assert math.isclose(wrap_angle(3.0 * math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(wrap_angle(-3.0 * math.pi), -math.pi, abs_tol=1e-5)


def test_pid_controller_arrived():
    controller = PIDPoseController(pos_tolerance=0.08, heading_tolerance=0.1)
    ctrl = controller.compute_control(
        current_x=1.0, current_y=1.0, current_theta=0.0,
        target_x=1.02, target_y=1.01, target_theta=0.02
    )
    assert ctrl.is_at_goal
    assert ctrl.linear_x == 0.0
    assert ctrl.angular_z == 0.0


def test_pid_controller_drive_forward():
    controller = PIDPoseController()
    ctrl = controller.compute_control(
        current_x=0.0, current_y=0.0, current_theta=0.0,
        target_x=2.0, target_y=0.0, target_theta=0.0
    )
    assert not ctrl.is_at_goal
    assert ctrl.linear_x > 0.0


def test_navigation_skills_navigate_to_simulated():
    odom = OdometryTracker(initial_x=0.0, initial_y=0.0, initial_theta=0.0)
    skills = NavigationSkills(
        odom_tracker=odom,
        control_rate_hz=50.0,
        default_timeout_s=5.0
    )

    res = skills.navigate_to(x=0.8, y=0.4, theta=0.0, sim_step=True)
    assert res.success
    assert res.reason == "arrived_within_tolerance"
    assert res.position_error_m <= 0.08


def test_navigation_skills_timeout_handling():
    odom = OdometryTracker(initial_x=0.0, initial_y=0.0, initial_theta=0.0)
    # Controller that won't move robot (sim_step=False so odom never updates)
    skills = NavigationSkills(
        odom_tracker=odom,
        control_rate_hz=100.0,
        default_timeout_s=0.1  # 100ms timeout
    )

    res = skills.navigate_to(x=2.0, y=2.0, timeout_s=0.05, sim_step=False)
    assert not res.success
    assert "timeout" in res.reason
    assert res.elapsed_time_s >= 0.05


def test_follow_waypoints_success():
    odom = OdometryTracker(initial_x=0.0, initial_y=0.0, initial_theta=0.0)
    skills = NavigationSkills(
        odom_tracker=odom,
        control_rate_hz=50.0,
        default_timeout_s=5.0
    )

    waypoints = [
        {"x": 0.5, "y": 0.0, "theta": 0.0, "name": "p1"},
        {"x": 0.5, "y": 0.5, "theta": 1.57, "name": "p2"},
    ]

    res = skills.follow_waypoints(waypoints, timeout_per_target_s=4.0, sim_step=True)
    assert res.success
    assert res.last_reached_index == 1
    assert "all_2_waypoints_reached" in res.reason


def test_stop_skill():
    odom = OdometryTracker(initial_x=1.0, initial_y=1.0, initial_theta=0.0)
    skills = NavigationSkills(odom_tracker=odom)

    res = skills.stop(reason="emergency")
    assert res.success
    assert "safely_stopped" in res.reason
    assert res.final_pose["x"] == 1.0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
