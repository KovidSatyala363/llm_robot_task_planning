import os
import json
import yaml
import re
from difflib import get_close_matches
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import httpx
from llm_robot_task_planning.skills.skill_registry import SKILL_REGISTRY

_ALLOWED_SKILLS = {"navigate_to", "follow_waypoints", "stop"}

# Accepted provider name aliases
PROVIDER_ALIASES = {
    "qwen": "qwen",
    "dashscope": "qwen",
    "cloud": "qwen",
    "ollama": "ollama",
    "local": "ollama",
    "llama": "ollama",
    "mock": "mock",
    "smartmock": "mock",
    "smart_mock": "mock",
    "smart-mock": "mock",
    "smarmock": "mock",
    "offline": "mock",
}


class LLMTaskPlanner:
    """Task planner with three brains: qwen (cloud), ollama (local), mock (offline rules).

    LLM_PROVIDER=<name> pins one brain (strict mode, no fallback); otherwise
    brains in LLM_PRIORITY/config are tried in order. Shell env vars override
    .env and config values.
    """

    def __init__(self, locations_yaml_path: str):
        self.locations_path = locations_yaml_path
        self.config_dir = os.path.dirname(locations_yaml_path)

        with open(locations_yaml_path, 'r') as f:
            self.locations = yaml.safe_load(f)['locations']

        self.yaml_config = self._load_yaml_config()
        self._reload_config(print_banner=True)

    def _load_yaml_config(self) -> dict:
        path = os.path.join(self.config_dir, 'llm_config.yaml')
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[LLMPlanner] Warning: could not read llm_config.yaml: {e}")
        return {}

    def _env_file_candidates(self) -> list:
        """Candidate .env paths, de-duplicated to existing files."""
        candidates = []
        try:
            from ament_index_python.packages import get_package_share_directory
            candidates.append(os.path.join(
                get_package_share_directory('llm_robot_task_planning'), '.env'))
        except Exception:
            pass
        candidates.append(os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '.env')))
        candidates.append(os.path.expanduser('~/ros2_ws/.env'))
        candidates.append(os.path.expanduser(
            '~/ros2_ws/src/llm_robot_task_planning/.env'))
        try:
            found = find_dotenv(usecwd=True)
            if found:
                candidates.append(found)
        except Exception:
            pass
        if os.getenv('LLM_ENV_FILE'):
            candidates.append(os.path.expanduser(os.getenv('LLM_ENV_FILE')))

        seen, out = set(), []
        for p in candidates:
            if p and p not in seen and os.path.exists(p):
                seen.add(p)
                out.append(os.path.abspath(p))
        return out

    def _load_env_files(self):
        # override=False: variables already exported in the shell win over .env
        for path in self._env_file_candidates():
            try:
                load_dotenv(path, override=False)
            except Exception:
                pass

    @staticmethod
    def _normalize(name: str):
        return PROVIDER_ALIASES.get((name or '').strip().lower())

    @staticmethod
    def _clean(value, default=''):
        """Treat empty strings / ${PLACEHOLDER} yaml values as unset."""
        if value is None:
            return default
        value = str(value).strip()
        if not value or value.startswith('${'):
            return default
        return value

    def _reload_config(self, print_banner: bool = False):
        # Re-read .env each time so provider changes apply without a restart.
        self._load_env_files()

        yaml_providers = self.yaml_config.get('llm', {}).get('providers', {}) or {}
        qcfg = yaml_providers.get('qwen', {}) or {}
        ocfg = yaml_providers.get('ollama', {}) or {}

        strict_provider = self._clean(os.getenv('LLM_PROVIDER', ''))
        if strict_provider:
            normalized = self._normalize(strict_provider)
            if normalized is None:
                raise ValueError(
                    f"Unknown LLM_PROVIDER='{strict_provider}'. "
                    f"Choose one of: qwen, ollama, mock")
            # Strict mode: pin this brain only. On failure retry the same
            # brain; never silently switch to another.
            self.priority = [normalized]
            self.strict_mode = True
        else:
            raw_priority = os.getenv('LLM_PRIORITY', '')
            if not raw_priority:
                raw_priority = ','.join(
                    self.yaml_config.get('llm', {}).get('priority', [])
                    or ['qwen', 'ollama', 'mock'])
            chain = []
            for token in raw_priority.split(','):
                norm = self._normalize(token)
                if norm and norm not in chain:
                    chain.append(norm)
            self.priority = chain or ['mock']
            self.strict_mode = False

        self.qwen_api_key = self._clean(os.getenv('QWEN_API_KEY', ''),
                                        self._clean(qcfg.get('api_key', '')))
        self.qwen_base_url = self._clean(os.getenv('QWEN_BASE_URL', ''),
                                         self._clean(qcfg.get('base_url', ''),
                                                     'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'))
        self.qwen_model = self._clean(os.getenv('QWEN_MODEL', ''),
                                      self._clean(qcfg.get('model', ''), 'qwen3.5-plus'))

        self.ollama_base_url = self._clean(os.getenv('OLLAMA_BASE_URL', ''),
                                           self._clean(ocfg.get('base_url', ''),
                                                       'http://localhost:11434/v1'))
        self.ollama_model = self._clean(os.getenv('OLLAMA_MODEL', ''),
                                        self._clean(ocfg.get('model', ''), 'llama3.2'))

        # trust_env=False: ignore system proxies, which break localhost Ollama
        self._qwen_http = httpx.Client(trust_env=False, follow_redirects=True, timeout=60.0)
        self._ollama_http = httpx.Client(trust_env=False, follow_redirects=True, timeout=180.0)

        if print_banner:
            self._print_banner()

    def _print_banner(self):
        if self.strict_mode:
            mode = (f"STRICT brain '{self.priority[0]}' ONLY "
                    f"(pinned via LLM_PROVIDER - no fallback to other brains)")
        else:
            mode = "fallback chain"
        print("[LLMPlanner] " + "=" * 62)
        print(f"[LLMPlanner] LLM brain mode : {mode}")
        print(f"[LLMPlanner] Active order   : {' -> '.join(self.priority)}")
        print(f"[LLMPlanner]   qwen   : model={self.qwen_model}  "
              f"key={'configured' if self.qwen_api_key else 'MISSING'}  "
              f"url={self.qwen_base_url}")
        print(f"[LLMPlanner]   ollama : model={self.ollama_model}  url={self.ollama_base_url}")
        print(f"[LLMPlanner]   mock   : smart offline rules (always available)")
        print("[LLMPlanner] " + "=" * 62)

    # Same-brain retries when a plan is unparseable, hallucinated or incomplete
    MAX_SAME_BRAIN_ATTEMPTS = 3

    def generate_plan(self, user_instruction: str) -> list:
        self._reload_config()

        prompt = self._build_prompt(user_instruction)
        wanted_pts = self._mentioned_destinations(user_instruction)

        for provider in self.priority:
            feedback = None  # corrective hint for the next same-brain attempt
            attempts = 1 if provider == "mock" else self.MAX_SAME_BRAIN_ATTEMPTS

            for attempt in range(1, attempts + 1):
                tag = provider if attempt == 1 else f"{provider} (attempt {attempt}/{attempts})"
                try:
                    if provider == "mock":
                        plan = self._normalize_plan(self._smart_mock_plan(user_instruction))
                        print("[LLMPlanner]  Success using 'mock' (smart offline planner)")
                        return plan

                    plan, method = self._plan_from_provider(provider, prompt, feedback)
                    if not plan:
                        print(f"[LLMPlanner]  '{tag}' returned no parseable plan")
                        feedback = ("You did not return any tool calls / JSON plan. "
                                    "Reply with the skill call(s) only.")
                        continue

                    # Drop hallucinated destinations, then canonicalize shape
                    plan = self._normalize_plan(self._sanitize_plan(plan, user_instruction))
                    if not plan:
                        print(f"[LLMPlanner]  '{tag}' plan matched no destination "
                              f"in the instruction")
                        feedback = self._missing_destination_feedback(wanted_pts, [])
                        continue

                    # Completeness: every requested destination must be covered
                    plan_pts = self._plan_destinations(plan)
                    if plan_pts and not wanted_pts:
                        # Movement planned but no destination could be matched
                        # to the instruction (typo too far / invented points):
                        # fail closed instead of driving to hallucinated places
                        print(f"[LLMPlanner]  '{tag}' planned movement to "
                              f"destination(s) not mentioned in the instruction")
                        feedback = self._unknown_destination_feedback()
                        continue
                    missing = [pt for pt in wanted_pts
                               if not any(abs(px - pt[0]) < 0.06 and abs(py - pt[1]) < 0.06
                                          for (px, py) in plan_pts)]
                    if wanted_pts and missing:
                        print(f"[LLMPlanner]  '{tag}' plan covers "
                              f"{len(wanted_pts) - len(missing)}/{len(wanted_pts)} "
                              f"requested destinations")
                        feedback = self._missing_destination_feedback(wanted_pts, missing)
                        continue

                    model = self.qwen_model if provider == 'qwen' else self.ollama_model
                    print(f"[LLMPlanner]  Success using '{provider}' "
                          f"(model={model}, interface={method}"
                          f"{'' if attempt == 1 else f', took {attempt} attempts'})")
                    return plan

                except Exception as e:
                    print(f"[LLMPlanner] '{tag}' failed: {e}")
                    feedback = (f"Your previous response caused an error: {e}. "
                                f"Reply again with a valid JSON plan / tool calls only.")

            if self.strict_mode:
                # Pinned brain: report failure instead of switching brains
                print(f"[LLMPlanner]  STRICT brain '{provider}' could not produce a "
                      f"complete, valid plan after {attempts} attempts.")
                print(f"[LLMPlanner]    No fallback is used because LLM_PROVIDER="
                      f"{provider} pins this brain. Check the brain/model and try again.")
                return []
            print(f"[LLMPlanner]  '{provider}' exhausted; trying next brain in the chain")

        print("[LLMPlanner]  All providers in the preference list failed. Returning empty plan.")
        return []

    def _missing_destination_feedback(self, wanted_pts: list, missing_pts: list) -> str:
        """Corrective re-prompt listing every required destination."""
        def name_of(x, y):
            for nm, loc in self.locations.items():
                if abs(float(loc['x']) - x) < 0.06 and abs(float(loc['y']) - y) < 0.06:
                    return nm
            return None

        lines = []
        for (x, y) in wanted_pts:
            nm = name_of(x, y)
            mark = "MISSING " if (x, y) in missing_pts or any(
                abs(x - mx) < 0.06 and abs(y - my) < 0.06 for (mx, my) in missing_pts) else ""
            lines.append(f"  - {mark}{(nm + ' ') if nm else ''}x={x}, y={y}")
        multi = ("TWO OR MORE destinations in total" if len(wanted_pts) >= 2
                 else "exactly ONE destination")
        skill = "follow_waypoints ONCE with ALL destinations in its waypoints array" \
                if len(wanted_pts) >= 2 else "navigate_to ONCE"
        return (
            "Your previous plan was INCOMPLETE. The instruction requires visiting "
            f"{len(wanted_pts)} destination(s). Rules:\n"
            f"- {multi} -> call {skill}, in the same order as the instruction.\n"
            f"- Never split the route into several calls; never omit a destination.\n"
            f"- Do NOT append a stop after the final destination.\n"
            f"Destinations required (in order):\n" + "\n".join(lines) +
            "\nRe-emit the COMPLETE plan now."
        )

    def _match_location(self, word: str):
        """Exact location name, or a near match for small typos (else None).

        e.g. 'inspect_table' -> 'inspection_table' (difflib, cutoff 0.75).
        """
        if word in self.locations:
            return word
        near = get_close_matches(word, list(self.locations.keys()), n=1, cutoff=0.75)
        return near[0] if near else None

    def _unknown_destination_feedback(self) -> str:
        names = ", ".join(sorted(self.locations.keys()))
        return (
            "Your previous plan called a movement skill, but the destination "
            "in the instruction matches NO known location (possibly a typo).\n"
            f"Known locations are: {names}.\n"
            "Use ONLY these locations (with their exact x, y, theta) or "
            "explicit coordinates written in the instruction. Never add "
            "extra waypoints. If the requested destination is not close to "
            "any known location, reply with an empty list []."
        )

    def _mentioned_destinations(self, instruction: str) -> list:
        """(x, y) of named locations / explicit coordinates, in mention order.

        Location names are matched fuzzily so small spelling mistakes
        ('inspect_table') still resolve to the intended location.
        """
        mentioned = []
        normalized = (instruction or "").lower()
        for loc in self.locations:
            if '_' in loc:
                normalized = normalized.replace(loc.replace('_', ' '), loc)
        for w in re.findall(r'\b[a-z_]+\b', normalized):
            loc_name = self._match_location(w)
            if loc_name:
                loc = self.locations[loc_name]
                pt = (float(loc['x']), float(loc['y']))
                if pt not in mentioned:
                    mentioned.append(pt)
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", normalized)
        if ("coordinate" in normalized or "point" in normalized or "x=" in normalized) and len(coords) >= 2:
            pt = (float(coords[0]), float(coords[1]))
            if pt not in mentioned:
                mentioned.append(pt)
        return mentioned

    @staticmethod
    def _plan_destinations(plan: list) -> list:
        """All (x, y) targets a plan visits, in order."""
        dests = []
        for call in plan or []:
            if not isinstance(call, dict):
                continue
            skill = call.get("skill")
            args = call.get("arguments", {}) or {}
            if skill == "navigate_to" and "x" in args and "y" in args:
                dests.append((float(args["x"]), float(args["y"])))
            elif skill == "follow_waypoints":
                for wp in args.get("waypoints", []) or []:
                    if isinstance(wp, dict) and "x" in wp and "y" in wp:
                        dests.append((float(wp["x"]), float(wp["y"])))
        return dests

    def _sanitize_plan(self, plan: list, instruction: str) -> list:
        """Drop destinations the model invented (not mentioned in the command)."""
        mentioned = self._mentioned_destinations(instruction)
        if not mentioned:
            # Nothing to verify against; the validator still checks the plan
            return plan

        def wanted(x, y):
            return any(abs(x - mx) < 0.06 and abs(y - my) < 0.06
                       for mx, my in mentioned)

        cleaned = []
        for call in plan:
            if not isinstance(call, dict):
                continue
            skill = call.get("skill")
            args = call.get("arguments", {}) or {}
            if skill == "navigate_to" and "x" in args and "y" in args:
                if wanted(float(args["x"]), float(args["y"])):
                    cleaned.append(call)
            elif skill == "follow_waypoints":
                wps = [wp for wp in (args.get("waypoints", []) or [])
                       if isinstance(wp, dict) and "x" in wp and "y" in wp
                       and wanted(float(wp["x"]), float(wp["y"]))]
                if wps:
                    cleaned.append({"skill": "follow_waypoints",
                                    "arguments": {"waypoints": wps}})
            else:
                cleaned.append(call)
        return cleaned

    @staticmethod
    def _normalize_plan(plan):
        """1 destination -> navigate_to; 2+ -> one follow_waypoints.

        A trailing stop after movement is dropped: arrival already halts
        the robot.
        """
        if not isinstance(plan, list):
            return plan

        out = []
        move_buffer = []  # consecutive destinations, flushed as one call

        def flush():
            if not move_buffer:
                return
            if len(move_buffer) == 1:
                wp = move_buffer[0]
                out.append({"skill": "navigate_to",
                            "arguments": {"x": wp["x"], "y": wp["y"],
                                          "theta": wp.get("theta", 0.0)}})
            else:
                out.append({"skill": "follow_waypoints",
                            "arguments": {"waypoints": [
                                {"x": wp["x"], "y": wp["y"],
                                 "theta": wp.get("theta", 0.0)}
                                for wp in move_buffer]}})
            move_buffer.clear()

        for call in plan:
            if not isinstance(call, dict):
                continue
            skill = call.get("skill")
            args = call.get("arguments", {}) or {}
            if skill == "navigate_to" and "x" in args and "y" in args:
                move_buffer.append({"x": float(args["x"]), "y": float(args["y"]),
                                    "theta": float(args.get("theta", 0.0))})
            elif skill == "follow_waypoints":
                for wp in args.get("waypoints", []) or []:
                    if isinstance(wp, dict) and "x" in wp and "y" in wp:
                        move_buffer.append({"x": float(wp["x"]), "y": float(wp["y"]),
                                            "theta": float(wp.get("theta", 0.0))})
            elif skill == "stop":
                flush()
                # Drop trailing stop after movement; keep a standalone stop
                if out and out[-1].get("skill") in ("navigate_to", "follow_waypoints"):
                    continue
                out.append({"skill": "stop", "arguments": {}})
            else:
                flush()
                out.append(call)
        flush()
        return out

    def _build_prompt(self, instruction: str) -> str:
        return (
            f"You are a robot task planner. Known locations: {json.dumps(self.locations)}\n"
            f"Available skills (functions): navigate_to(x,y,theta), "
            f"follow_waypoints(waypoints), stop().\n"
            f"Skill selection rules (follow them EXACTLY):\n"
            f"1. If the instruction names exactly ONE destination, call navigate_to ONCE.\n"
            f"2. If it names TWO OR MORE destinations to visit in order, call "
            f"follow_waypoints ONCE and put EVERY destination in its waypoints array "
            f"in the same order. NEVER emit several separate navigate_to calls and "
            f"NEVER omit any requested destination.\n"
            f"3. Do NOT add a stop after the final destination: arriving already stops "
            f"the robot.\n"
            f"4. Use ONLY locations from the known-locations list above; use each "
            f"location's exact x, y, theta.\n"
            f"Example A - 'go to storage' -> "
            f"navigate_to(x=-1.4, y=-1.2, theta=3.1415).\n"
            f"Example B - 'go to inspection_table then workbench and stop' -> "
            f"follow_waypoints(waypoints=["
            f"{{x:1.4,y:1.2,theta:0.0}},{{x:1.4,y:-1.2,theta:0.0}}]) "
            f"(one call, both points, no stop).\n"
            f"Instruction: '{instruction}'\n"
            f"Call the skill functions in the required order. If function calling is "
            f"not available, output ONLY a JSON list, e.g. "
            f"[{{\"skill\":\"navigate_to\",\"arguments\":{{\"x\":1.0,\"y\":2.0,\"theta\":0.0}}}}]"
        )

    def _client_for(self, provider: str):
        """Return (OpenAI client, model name) for qwen or ollama."""
        if provider == "qwen":
            if not self.qwen_api_key or not self.qwen_api_key.startswith("sk-"):
                raise ValueError("QWEN_API_KEY is missing or invalid (must start with 'sk-')")
            return OpenAI(
                api_key=self.qwen_api_key,
                base_url=self.qwen_base_url,
                http_client=self._qwen_http,
            ), self.qwen_model
        return OpenAI(
            api_key="ollama",  # local Ollama ignores the key; client needs non-empty
            base_url=self.ollama_base_url,
            http_client=self._ollama_http,
        ), self.ollama_model

    def _plan_from_provider(self, provider: str, prompt: str, feedback: str = None):
        """Return (plan, interface). Tries function calling, then JSON-in-text.

        feedback is a corrective message from a previous attempt of the same
        brain.
        """
        client, model = self._client_for(provider)
        messages = [{"role": "user", "content": prompt}]
        if feedback:
            # Standard multi-turn correction: acknowledge then re-instruct
            messages.append({"role": "assistant", "content": "Understood."})
            messages.append({"role": "user", "content": feedback})
        # Disabling Qwen's thinking phase speeds up tool calls (ignored by Ollama)
        extra = {"enable_thinking": False} if provider == "qwen" else {}

        # Try OpenAI-compatible function calling first
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=SKILL_REGISTRY,
                tool_choice="auto",
                temperature=0.0,
                extra_body=extra,
            )
            msg = resp.choices[0].message
            plan = self._tool_calls_to_plan(msg)
            if plan:
                return plan, "function-calling"
            # Some models reply with JSON text even when tools are offered
            plan = self._parse_json((msg.content or "").strip())
            if plan:
                return plan, "function-calling(json)"
        except Exception as e:
            print(f"[LLMPlanner]   function-calling unavailable for '{provider}': {e}")
            print(f"[LLMPlanner]   falling back to JSON prompt for '{provider}'")

        # Fallback: parse JSON out of a plain completion
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            extra_body=extra,
        )
        raw = (resp.choices[0].message.content or "").strip()
        plan = self._parse_json(raw)
        if plan:
            return plan, "json-prompt"
        return None, None

    @staticmethod
    def _tool_calls_to_plan(message) -> list:
        """Convert OpenAI tool_calls into internal skill-call dicts."""
        plan = []
        tool_calls = getattr(message, "tool_calls", None) or []
        for call in tool_calls:
            name = getattr(call.function, "name", "")
            if name not in _ALLOWED_SKILLS:
                continue
            try:
                args = json.loads(call.function.arguments or "{}")
            except Exception:
                continue
            if not isinstance(args, dict):
                continue
            if name == "stop":
                args = {}
            plan.append({"skill": name, "arguments": args})
        return plan

    def _parse_json(self, raw: str) -> list:
        raw = (raw or "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _smart_mock_plan(self, text: str) -> list:
        text_lower = text.lower()
        # Match spaced names, e.g. "charging station" -> "charging_station"
        normalized = text_lower
        for loc in self.locations:
            if '_' in loc:
                normalized = normalized.replace(loc.replace('_', ' '), loc)

        plan = []
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", normalized)
        if ("coordinate" in normalized or "point" in normalized or "x=" in normalized) and len(coords) >= 2:
            plan.append({
                "skill": "navigate_to",
                "arguments": {"x": float(coords[0]), "y": float(coords[1]), "theta": 0.0}
            })
            return plan

        words = re.findall(r'\b[a-z_]+\b', normalized)
        visited = []
        for w in words:
            loc_name = self._match_location(w)
            if loc_name and loc_name not in visited:
                visited.append(loc_name)

        if len(visited) > 1:
            waypoints = [
                {"x": self.locations[loc]['x'], "y": self.locations[loc]['y'],
                 "theta": self.locations[loc]['theta']}
                for loc in visited
            ]
            plan.append({"skill": "follow_waypoints", "arguments": {"waypoints": waypoints}})
        elif len(visited) == 1:
            loc = self.locations[visited[0]]
            plan.append({"skill": "navigate_to",
                         "arguments": {"x": loc['x'], "y": loc['y'], "theta": loc['theta']}})

        if "stop" in normalized:
            plan.append({"skill": "stop", "arguments": {}})
        return plan
