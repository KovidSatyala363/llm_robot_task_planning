from pydantic import ValidationError
from llm_robot_task_planning.skills.skill_interface import NavigateToArgs, FollowWaypointsArgs, StopArgs

class PlanValidator:
    ALLOWED_SKILLS = {"navigate_to", "follow_waypoints", "stop"}

    def __init__(self, x_bounds=(-2.3, 2.3), y_bounds=(-2.3, 2.3), max_steps=10):
        self.x_min, self.x_max = x_bounds
        self.y_min, self.y_max = y_bounds
        self.max_steps = max_steps

    def validate_plan(self, plan: list[dict]) -> tuple[bool, str]:
        if not isinstance(plan, list):
            return False, "Plan must be a list of skill calls"
        if len(plan) == 0:
            return False, "Plan is empty"
        if len(plan) > self.max_steps:
            return False, f"Plan exceeds maximum allowed steps ({len(plan)} > {self.max_steps})"

        for idx, call_dict in enumerate(plan):
            valid, msg = self.validate_call(call_dict)
            if not valid:
                return False, f"Step {idx+1} invalid: {msg}"
        return True, "Plan valid"

    def validate_call(self, call_dict: dict) -> tuple[bool, str]:
        skill = call_dict.get("skill")
        if skill not in self.ALLOWED_SKILLS:
            return False, f"Skill '{skill}' is not in allowlist: {list(self.ALLOWED_SKILLS)}"

        args = call_dict.get("arguments", {})
        try:
            if skill == "navigate_to":
                parsed = NavigateToArgs(**args)
                if not (self.x_min <= parsed.x <= self.x_max and self.y_min <= parsed.y <= self.y_max):
                    return False, f"Target ({parsed.x}, {parsed.y}) is outside workspace bounds [{self.x_min}, {self.x_max}], [{self.y_min}, {self.y_max}]"
            elif skill == "follow_waypoints":
                parsed = FollowWaypointsArgs(**args)
                for wp in parsed.waypoints:
                    if not (self.x_min <= wp.x <= self.x_max and self.y_min <= wp.y <= self.y_max):
                        return False, f"Waypoint ({wp.x}, {wp.y}) outside workspace bounds"
            elif skill == "stop":
                StopArgs(**args)
        except ValidationError as e:
            return False, f"Argument validation error: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"

        return True, "Valid"
