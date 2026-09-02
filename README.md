# LLM-Assisted Mobile Robot Task Planning

**An autonomous mobile robot task planning system using Large Language Models (LLM), ROS 2 Humble, and Webots R2025a simulation.**

---

## Overview

This project demonstrates a **safe and modular** framework for translating natural language instructions into executable robot commands. It combines:

- **LLM (OpenAI or local)**: Converts user instructions into structured tool calls (skills).
- **Deterministic Safety Validator**: Enforces strict allowlists, spatial bounds, and typed argument schemas before any command is sent to the robot.
- **Closed‑Loop Controller**: A real‑time PID controller (20 Hz) drives a differential‑drive robot in the Webots simulator, using GPS and IMU odometry.
- **ROS 2 Humble**: Manages inter‑node communication and launch files.

The system is tested in a simulated laboratory environment with landmarks (storage, workbench, charging dock, etc.) and ensures zero safety violations.

---

## Architecture
User Instruction (Natural Language)
│
▼
┌─────────────────────┐
│ LLM Planner │ → Generates Tool Call Sequence (JSON)
└─────────────────────┘
│
▼
┌─────────────────────┐
│ Safety Validator │ → Checks Allowlist, Bounds & Typed Schemas
└─────────────────────┘
│ (If Approved)
▼
┌─────────────────────┐
│ Navigation Node │ → Closed‑Loop PID Control (navigate_to, stop)
└─────────────────────┘
│
▼
┌─────────────────────┐
│ Webots 'agent0' │ → Mobile Base in Simulated Lab Arena (ENU)
└─────────────────────┘
│
▼
┌─────────────────────┐
│ Feedback Log │ → Structured JSON Result (Elapsed Time, Pos Error)
└─────────────────────┘

---

## Features

- **Natural Language to Action**: Users can say *“Go to storage”* or *“Visit workbench then stop”*.
- **Strict Safety**: Every command is validated against:
  - Allowlist of skills: `navigate_to`, `follow_waypoints`, `stop`
  - Workspace boundaries: `[-2.3, 2.3]` meters in both X and Y
  - Type conformance and argument ranges
- **Simulation Environment**: Webots R2025a with a RoboMaster‑like differential‑drive robot.
- **Real‑time Control**: PID controller with smooth acceleration and final orientation alignment.
- **Structured Logging**: Each skill execution returns JSON with success, error, position error, and time.

---

## Prerequisites

- **Ubuntu 22.04 LTS** 
- **ROS 2 Humble** 
- **Webots R2025a** 
- **Python 3.10+** 

---

## Installation & Build

Clone the repository into your ROS 2 workspace and build:

```bash
cd ~/ros2_ws/src
git clone https://github.com/KovidSatyala363/llm_robot_task_planning.git
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash

## Configuration

### 1. Location Mapping (`config/locations.yaml`)

Define named locations with their (x, y, theta) coordinates. Example:

```yaml
storage:
  x: -1.4
  y: -1.2
  theta: 3.1415
workbench:
  x: 1.4
  y: -1.2
  theta: 0.0
charging_station:
  x: -1.4
  y: 1.2
  theta: 3.1415
inspection_table:
  x: 1.4
  y: 1.2
  theta: 0.0
center_hub:
  x: 0.0
  y: 0.0
  theta: 0.0
  
  ### 2. Workspace Bounds (config/workspace_bounds.yaml)
  Set the allowed spatial limits:
  x_min: -2.3
  x_max: 2.3
  y_min: -2.3
  y_max: 2.3
  
  ### 3. LLM Planner (`llm_planner.py`)

The planner runs in two modes:

- **Offline Mock Mode** – No API key, internet, or external services. Uses deterministic regex rules to parse instructions, extract location names, and look up `(x, y, theta)` from `config/locations.yaml`. Safe, repeatable, and predictable.

- **OpenAI Mode** – If you set `OPENAI_API_KEY`, it will call `gpt-4o-mini`. On any failure, it automatically falls back to the offline mock mode. **By default, no API key is required or used** – the system runs entirely offline.

### Usage
Launch the Full System

Run the main launch file, which starts Webots, the bridge node, the navigation node, and the task agent:
ros2 launch llm_robot_task_planning full_system_launch.py

The Webots simulation window will open, and the task agent terminal will prompt:
Enter Instruction >

Type a natural language command, e.g.:

    "go to storage"

    "visit storage then workbench and stop"

    "go to charging station"

    "go to coordinate 1.2 -0.5"

The system will:

   1) Call the LLM to generate a tool sequence.
   2)Validate the plan.
   3)Execute the navigation skills in order.
   4)Print results and return to the prompt.
   
# Terminal 1: Webots and bridge
ros2 launch llm_robot_task_planning robot_launch.py

# Terminal 2: Navigation controller
ros2 run llm_robot_task_planning navigation_node

# Terminal 3: Task agent (LLM planner)
ros2 run llm_robot_task_planning task_agent_node




