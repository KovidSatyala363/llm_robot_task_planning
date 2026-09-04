#!/usr/bin/env bash
# ==============================================================================
# One-command launcher for the LLM robot task planning system (Webots + ROS 2).
#
# Usage:
#   ./scripts/run_system.sh qwen     # Qwen cloud API brain
#   ./scripts/run_system.sh ollama   # local Ollama brain (llama3.2)
#   ./scripts/run_system.sh mock     # smart offline mock brain (no network)
#
# This script starts the ROBOT side in this terminal (Webots + bridge +
# navigation) and opens a SECOND terminal window for the interactive agent
# (ros2 launch cannot forward keyboard input, so the agent must run via
# 'ros2 run' in its own terminal). If no GUI terminal is available it prints
# the exact command to copy-paste.
# ==============================================================================
set -e

PROVIDER="${1:-}"

case "$PROVIDER" in
  qwen|ollama|mock|smartmock|smarmock|offline) ;;
  *)
    echo "Usage: $0 <qwen|ollama|mock>"
    echo ""
    echo "  qwen    -> Qwen / DashScope cloud API (needs QWEN_API_KEY in .env)"
    echo "  ollama  -> local Ollama server (starts 'ollama serve' if needed)"
    echo "  mock    -> smart offline rule-based planner (no network/API key)"
    exit 1
    ;;
esac

# Normalize mock aliases
case "$PROVIDER" in
  smartmock|smarmock|offline) PROVIDER=mock ;;
esac

# ---- Source ROS 2 and the workspace -------------------------------------------
source /opt/ros/humble/setup.bash
if [ -f "$HOME/ros2_ws/install/setup.bash" ]; then
  source "$HOME/ros2_ws/install/setup.bash"
fi
export WEBOTS_HOME="${WEBOTS_HOME:-/usr/local/webots}"

# ---- Make sure the Ollama server is up when ollama is selected ----------------
if [ "$PROVIDER" = "ollama" ]; then
  if ! curl -s --max-time 2 http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "[run_system] Starting Ollama server in the background..."
    nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
    sleep 3
  fi
  echo "[run_system] Ollama models available:"
  ollama list || true
fi

# ---- Interactive agent command (runs in its OWN terminal) ---------------------
AGENT_CMD="source /opt/ros/humble/setup.bash; source $HOME/ros2_ws/install/setup.bash; \
export LLM_PROVIDER=$PROVIDER; \
echo 'Brain: $PROVIDER - wait for the Enter Instruction > prompt, then type a command.'; \
ros2 run llm_robot_task_planning task_agent_node; exec bash"

open_agent_terminal() {
  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -c "$AGENT_CMD"
  elif command -v konsole >/dev/null 2>&1; then
    konsole -e bash -c "$AGENT_CMD" &
  elif command -v xterm >/dev/null 2>&1; then
    xterm -e bash -c "$AGENT_CMD" &
  else
    return 1
  fi
}

echo "[run_system] Robot brain selected: $PROVIDER"
if open_agent_terminal; then
  echo "[run_system] Opened a new terminal for the interactive agent."
else
  echo ""
  echo "[run_system] Could not open a new terminal automatically."
  echo "           Open a SECOND terminal manually and run:"
  echo "------------------------------------------------------------"
  echo "  source /opt/ros/humble/setup.bash"
  echo "  source ~/ros2_ws/install/setup.bash"
  echo "  LLM_PROVIDER=$PROVIDER ros2 run llm_robot_task_planning task_agent_node"
  echo "------------------------------------------------------------"
  echo ""
fi

echo "[run_system] Starting Webots + bridge + navigation in this terminal..."
echo "[run_system] (in the agent terminal, type commands when you see 'Enter Instruction >')"
ros2 launch llm_robot_task_planning robot_launch.py
