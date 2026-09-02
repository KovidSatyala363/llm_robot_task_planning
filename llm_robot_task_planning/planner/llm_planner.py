import os
import json
import yaml
import re

class LLMTaskPlanner:
    """Task Planner supporting both Real OpenAI Tool Calling and Offline Smart Mock."""
    def __init__(self, locations_yaml_path: str):
        with open(locations_yaml_path, 'r') as f:
            self.locations = yaml.safe_load(f)['locations']

    def generate_plan(self, user_instruction: str) -> list[dict]:
        api_key = os.environ.get("OPENAI_API_KEY")

        # 1. Real LLM Call (if API key is present)
        if api_key and api_key.startswith("sk-"):
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                prompt = (
                    f"You are a mobile robot task planning agent.\n"
                    f"Available locations: {json.dumps(self.locations)}\n"
                    f"Allowed skills: navigate_to(x, y, theta), follow_waypoints(waypoints), stop().\n"
                    f"User instruction: '{user_instruction}'\n"
                    f"Convert this instruction into a JSON list of skill calls.\n"
                    f"Output ONLY the JSON list, for example: [{{'skill': 'navigate_to', 'arguments': {{'x': 1.4, 'y': -1.2, 'theta': 0.0}}}}]"
                )
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                raw_text = response.choices[0].message.content.strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                return json.loads(raw_text)
            except Exception as e:
                print(f"[LLMPlanner] Note: Real LLM API call failed ({e}). Using smart mock planner.")

        # 2. Smart Mock Planner (Deterministic Tool-Calling Engine)
        return self._smart_mock_plan(user_instruction)

    def _smart_mock_plan(self, text: str) -> list[dict]:
        text_lower = text.lower()
        plan = []

        # Check for explicit coordinate requests, e.g. (5.0, 5.0)
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", text_lower)
        if ("coordinate" in text_lower or "point" in text_lower or "x=" in text_lower) and len(coords) >= 2:
            plan.append({
                "skill": "navigate_to",
                "arguments": {"x": float(coords[0]), "y": float(coords[1]), "theta": 0.0}
            })
            return plan

        # Extract sequence of named locations
        words = re.findall(r'\b[a-z_]+\b', text_lower)
        visited = []
        for word in words:
            if word in self.locations and word not in visited:
                visited.append(word)

        for loc_name in visited:
            loc = self.locations[loc_name]
            plan.append({
                "skill": "navigate_to",
                "arguments": {"x": loc['x'], "y": loc['y'], "theta": loc['theta']}
            })

        if "stop" in text_lower or (len(plan) > 0 and "and stop" in text_lower):
            plan.append({"skill": "stop", "arguments": {}})

        return plan
