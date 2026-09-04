# LLM-Assisted Mobile Robot Task Planning

A differential-drive robot in a Webots laboratory that receives **natural-language
instructions** and executes them as a small, **validated** sequence of high-level
skills. ROS 2 Humble + Webots R2025a, Python 3.10.

```
User instruction (natural language)
        │
        ▼
┌────────────────────┐   tool calls (JSON)   ┌──────────────────────┐
│  LLM Task Planner  │ ───────────────────▶ │  Safety Validator     │
│  qwen / ollama /   │                       │  allowlist + types +  │
│  smart mock        │ ◀───────────────────  │  workspace bounds     │
└────────────────────┘   structured result   └──────────┬───────────┘
                                                        │ approved
                                                        ▼
                                            ┌──────────────────────┐
                                            │  Navigation Node      │
                                            │  closed-loop PID 20Hz │
                                            └──────────┬───────────┘
                                                        │ /agent0/cmd_vel
                                                        ▼
                                            ┌──────────────────────┐
                                            │  Webots robot agent0 │
                                            └──────────────────────┘
```

## The three LLM brains

| Brain | What it is | Set with |
|---|---|---|
| `qwen` | Qwen / DashScope cloud model (OpenAI-compatible API). Key in `.env` (`QWEN_API_KEY`). | `LLM_PROVIDER=qwen` |
| `ollama` | Local model (`llama3.2`) via a local Ollama server, no internet/key. | `LLM_PROVIDER=ollama` |
| `mock` | Smart offline rule-based planner. Always available, instant, deterministic. | `LLM_PROVIDER=mock` |

`LLM_PROVIDER` **pins** the brain: only the selected brain is ever used (no silent
switching). If its plan misses a destination it is retried (same brain, up to 3
attempts with corrective feedback); if it still fails the agent reports the
failure and sends nothing to the robot.

Every brain produces the same plan shape:

- one destination (e.g. `"go to storage"`) → one `navigate_to(x, y, theta)`
- two or more destinations (e.g. `"visit storage then workbench and stop"`) →
  one `follow_waypoints(waypoints=[...])` that visits them in order
- a trailing `stop` is dropped (arrival already halts the robot)

## Skills

- `navigate_to(x, y, theta)` — drive to a pose; reports success only inside the
  position (0.25 m) and heading (0.35 rad) tolerances; 35 s per-leg timeout.
- `follow_waypoints(waypoints)` — visit poses in sequence; on failure the result
  reports `waypoint_reached_idx`, the index of the last waypoint fully reached.
- `stop()` — publish zero velocity immediately.

Every result is structured JSON: `skill, success, reason, position_error_m,
elapsed_time_s, waypoint_reached_idx`.

## Safety

Before execution every plan is checked by an independent validator:

1. **Allowlist** — only `navigate_to`, `follow_waypoints`, `stop` are accepted.
2. **Typed arguments** — Pydantic schemas reject missing/malformed fields.
3. **Workspace bounds** — every target must be inside `[-2.3, 2.3]` m.
4. **Plan size** — at most 10 steps.
5. **Grounding** — every target coordinate must match a location named in the
   instruction (small spelling mistakes are matched fuzzily, e.g.
   `inspect_table` → `inspection_table`); invented waypoints are stripped. If
   movement is planned but no destination can be matched at all, the plan is
   rejected and the robot does not move.

The LLM never emits velocity commands or code; it only proposes skill calls.

## Recovery

After each skill the agent inspects the structured result. On a **timeout**
fault the same call is retried **at most once** (bounded); any other fault
(unknown skill, rejected plan) aborts the task. Every decision
(`proceed` / `retry_once` / `abort`) is logged with the original plan, observed
result, and final outcome.

## Install & build

```bash
cd ~/ros2_ws/src
git clone <your-repo-url> llm_robot_task_planning   # or copy the package here
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select llm_robot_task_planning
source install/setup.bash
pip install -r src/llm_robot_task_planning/requirements.txt
```

Configure the LLM brains by copying the template and editing it:

```bash
cd src/llm_robot_task_planning
cp .env.example .env        # .env is git-ignored: never commit your real key
```

For the qwen brain, put your DashScope key (starts with `sk-`) in `.env` as
`QWEN_API_KEY=sk-...`. The mock and ollama brains need no key. For ollama:
`ollama serve` once and `ollama pull llama3.2`.

## Run (two terminals)

**Terminal 1 — simulation + bridge + navigation:**

```bash
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
ros2 launch llm_robot_task_planning robot_launch.py
```

**Terminal 2 — interactive task agent (pick one brain):**

```bash
cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash
LLM_PROVIDER=mock   ros2 run llm_robot_task_planning task_agent_node   # offline
LLM_PROVIDER=ollama ros2 run llm_robot_task_planning task_agent_node   # local LLM
LLM_PROVIDER=qwen   ros2 run llm_robot_task_planning task_agent_node   # cloud LLM
```

At `Enter Instruction >` type, for example:

```
go to storage
visit inspection_table then workbench and stop
go to entrance then center_hub and stop
go to coordinate 1.0 -0.5
go to coordinate 5.0 5.0          # rejected: outside workspace
```


## Package layout

```
config/        locations.yaml, workspace_bounds.yaml, llm_config.yaml
launch/        robot_launch.py (Webots+bridge+navigation), task_agent_launch.py
llm_robot_task_planning/
  nodes/       task_agent_node, navigation_node, webots_bridge_node, keyboard_twist
  planner/     llm_planner (3 brains), plan_validator, recovery_handler
  skills/      skill_registry (LLM tools), skill_interface (Pydantic contracts)
  controllers/ pid_controller, odometry_tracker
worlds/        lab_world.wbt
tests/         planner, validator, skills unit tests
RESULTS.md     measured outcomes per instruction
report/        LaTeX technical report
```
