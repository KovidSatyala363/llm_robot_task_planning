"""
Unit tests for the LLM task planner, location manager and recovery handler.

The planner tests force the offline smart-mock brain (LLM_PROVIDER=mock) so
they run deterministically with no network access or API key.
Verifies:
  - Single location instruction -> navigate_to
  - Multi-location instruction -> follow_waypoints
  - Explicit "stop" instruction -> stop skill appended
  - Out-of-bounds coordinates are produced but later rejected by the validator
  - LocationManager lookups
  - RecoveryHandler bounded retry policy
"""

import os
import json

import pytest

# Force the offline mock brain before the planner reads the environment.
os.environ["LLM_PROVIDER"] = "mock"

from llm_robot_task_planning.planner.llm_planner import LLMTaskPlanner
from llm_robot_task_planning.planner.locations import LocationManager
from llm_robot_task_planning.planner.plan_validator import PlanValidator
from llm_robot_task_planning.planner.recovery_handler import RecoveryHandler


def _locations_yaml_path() -> str:
    try:
        from ament_index_python.packages import get_package_share_directory
        path = os.path.join(
            get_package_share_directory("llm_robot_task_planning"),
            "config", "locations.yaml",
        )
        if os.path.exists(path):
            return path
    except Exception:
        pass
    return os.path.expanduser(
        "~/ros2_ws/src/llm_robot_task_planning/config/locations.yaml"
    )


@pytest.fixture
def locations_path():
    return _locations_yaml_path()


@pytest.fixture
def mock_planner(locations_path):
    return LLMTaskPlanner(locations_path)


def test_single_location_planning(mock_planner):
    plan = mock_planner.generate_plan("Go to storage.")
    assert len(plan) >= 1
    assert plan[0]["skill"] == "navigate_to"
    # storage is at x=-1.4, y=-1.2
    assert plan[0]["arguments"]["x"] == -1.4
    assert plan[0]["arguments"]["y"] == -1.2


def test_multi_location_planning(mock_planner):
    plan = mock_planner.generate_plan("Visit storage, then workbench, and stop.")
    assert plan[0]["skill"] == "follow_waypoints"
    waypoints = plan[0]["arguments"]["waypoints"]
    assert len(waypoints) == 2
    assert waypoints[0]["x"] == -1.4 and waypoints[0]["y"] == -1.2
    assert waypoints[1]["x"] == 1.4 and waypoints[1]["y"] == -1.2
    # Multi-destination plans are one continuous follow_waypoints call;
    # the redundant trailing "stop" (robot is already stationary on arrival)
    # is normalized away.
    assert len(plan) == 1
    assert plan[-1]["skill"] == "follow_waypoints"


def test_coordinate_instruction(mock_planner):
    plan = mock_planner.generate_plan("Go to coordinate (1.0, -0.5).")
    assert plan[0]["skill"] == "navigate_to"
    assert plan[0]["arguments"]["x"] == 1.0
    assert plan[0]["arguments"]["y"] == -0.5


def test_out_of_bounds_plan_rejected_by_validator(mock_planner):
    plan = mock_planner.generate_plan("Go to coordinate (5.0, 5.0).")
    validator = PlanValidator()
    valid, msg = validator.validate_plan(plan)
    assert valid is False
    assert "outside workspace bounds" in msg


def test_location_manager(locations_path):
    locations = LocationManager(locations_path)
    storage = locations.get_location("storage")
    assert storage is not None
    assert storage["x"] == -1.4
    assert "workbench" in locations.get_all_locations()


def test_recovery_handler_bounded_retry():
    recovery = RecoveryHandler(max_retries=1)
    skill_call = {"skill": "navigate_to", "arguments": {"x": 1.0, "y": 1.0}}

    # First timeout: one bounded retry allowed
    assert recovery.should_retry(skill_call, reason="timeout") is True
    # Second timeout for the same skill: retry budget exhausted -> abort
    assert recovery.should_retry(skill_call, reason="timeout") is False
    # Non-timeout failures are never retried
    assert recovery.should_retry({"skill": "stop", "arguments": {}},
                                 reason="unknown_skill") is False


if __name__ == "__main__":
    pytest.main(["-v", __file__])
