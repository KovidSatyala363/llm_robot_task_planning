"""
Unit Tests for LLM Task Planner & Recovery Loop (Part 4)
Verifies:
  - Single location prompt translation to navigate_to
  - Multi-location prompt translation to follow_waypoints and stop
  - Out-of-bounds location handling
  - End-to-end TaskAgent workflow
"""

import pytest
from llm_robot_task_planning.planner.llm_planner import LLMTaskPlanner
from llm_robot_task_planning.planner.locations import LandmarkDatabase
from llm_robot_task_planning.planner.recovery_handler import RecoveryHandler, RecoveryActionType
from llm_robot_task_planning.nodes.task_agent_node import TaskAgent
from llm_robot_task_planning.skills.skill_interface import SkillResult


@pytest.fixture
def offline_planner():
    return LLMTaskPlanner(use_mock=True)


def test_single_location_planning(offline_planner):
    plan = offline_planner.plan("Go to storage.")
    assert len(plan) >= 1
    assert plan[0]["skill"] == "navigate_to"
    # Storage is at x=-1.6, y=1.2
    assert plan[0]["arguments"]["x"] == -1.6
    assert plan[0]["arguments"]["y"] == 1.2


def test_multi_location_and_stop_planning(offline_planner):
    plan = offline_planner.plan("Visit storage, then workbench, and stop.")
    assert len(plan) >= 2
    # First skill is follow_waypoints or navigate_to
    assert plan[0]["skill"] == "follow_waypoints"
    waypoints = plan[0]["arguments"]["waypoints"]
    assert len(waypoints) == 2
    assert waypoints[0]["name"] == "storage"
    assert waypoints[1]["name"] == "workbench"

    # Final skill is stop
    assert plan[-1]["skill"] == "stop"


def test_recovery_handler_retry_on_timeout():
    recovery = RecoveryHandler(max_retries=1)

    timeout_result = SkillResult(
        success=False,
        reason="timeout (exceeded 25.0s)",
        elapsed_time_s=25.1
    )

    decision = recovery.evaluate_result("navigate_to", {"x": 1.0, "y": 1.0}, timeout_result, step_index=0)
    assert decision.action == RecoveryActionType.RETRY_ONCE

    # If it fails again, should abort
    decision2 = recovery.evaluate_result("navigate_to", {"x": 1.0, "y": 1.0}, timeout_result, step_index=0)
    assert decision2.action == RecoveryActionType.SAFE_ABORT


def test_task_agent_end_to_end_valid():
    agent = TaskAgent(use_mock_llm=True, sim_step=True)
    res = agent.execute_instruction("Go to workbench and stop.")
    assert res["status"] == "COMPLETED_SUCCESS"
    assert res["overall_success"] is True
    assert res["total_steps_in_plan"] >= 1


def test_task_agent_rejects_out_of_bounds():
    agent = TaskAgent(use_mock_llm=True, sim_step=True)
    res = agent.execute_instruction("Go to outer_space at x=15.0, y=30.0.")
    assert res["status"] == "REJECTED_BY_VALIDATOR"
    assert res["rejection_code"] == "OUT_OF_BOUNDS"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
