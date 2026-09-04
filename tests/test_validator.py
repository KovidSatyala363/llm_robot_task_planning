import pytest
from llm_robot_task_planning.planner.plan_validator import PlanValidator

def test_valid_plan():
    validator = PlanValidator()
    plan = [
        {"skill": "navigate_to", "arguments": {"x": 1.0, "y": -1.0, "theta": 0.0}},
        {"skill": "stop", "arguments": {}}
    ]
    valid, msg = validator.validate_plan(plan)
    assert valid is True

def test_out_of_bounds_plan():
    validator = PlanValidator()
    plan = [{"skill": "navigate_to", "arguments": {"x": 5.0, "y": 5.0, "theta": 0.0}}]
    valid, msg = validator.validate_plan(plan)
    assert valid is False
    assert "outside workspace bounds" in msg

def test_unknown_skill_rejected():
    validator = PlanValidator()
    plan = [{"skill": "delete_all_files", "arguments": {}}]
    valid, msg = validator.validate_plan(plan)
    assert valid is False
    assert "not in allowlist" in msg
