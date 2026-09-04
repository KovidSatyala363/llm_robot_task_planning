import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
import sys
import time
from ament_index_python.packages import get_package_share_directory
from llm_robot_task_planning.planner.llm_planner import LLMTaskPlanner
from llm_robot_task_planning.planner.plan_validator import PlanValidator
from llm_robot_task_planning.planner.recovery_handler import RecoveryHandler

class TaskAgentNode(Node):
    # Result wait budgets per skill (follow_waypoints may contain several legs)
    RESULT_TIMEOUT_S = {"stop": 15.0, "navigate_to": 70.0, "follow_waypoints": 140.0}
    DEFAULT_TIMEOUT_S = 70.0
    HEARTBEAT_S = 15.0

    def __init__(self):
        super().__init__('task_agent_node')

        try:
            pkg_dir = get_package_share_directory('llm_robot_task_planning')
            loc_path = os.path.join(pkg_dir, 'config', 'locations.yaml')
        except Exception:
            loc_path = os.path.expanduser('~/ros2_ws/src/llm_robot_task_planning/config/locations.yaml')

        self.planner = LLMTaskPlanner(loc_path)
        self.validator = PlanValidator()
        self.recovery = RecoveryHandler(max_retries=1)

        self.skill_pub = self.create_publisher(String, '/agent0/execute_skill', 10)
        self.result_sub = self.create_subscription(String, '/agent0/skill_result', self.result_callback, 10)
        self.latest_result = None
        self.get_logger().info("Task Agent initialized.")

    def result_callback(self, msg: String):
        self.latest_result = json.loads(msg.data)

    def wait_for_navigation(self, timeout_s: float = 60.0) -> bool:
        """Wait until the navigation node subscribes to execute_skill.

        Without this, the first command can be published before DDS
        discovery completes and be silently lost.
        """
        if self.skill_pub.get_subscription_count() > 0:
            return True
        print(" Waiting for the navigation stack (Webots + bridge + "
              "navigation in Terminal 1)...", flush=True)
        deadline = time.time() + timeout_s
        dots = 0
        while time.time() < deadline and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.2)
            if self.skill_pub.get_subscription_count() > 0:
                print(" Navigation node connected.\n", flush=True)
                return True
            dots += 1
            if dots % 10 == 0:
                print("   ...still waiting for Terminal 1 "
                      "(ros2 launch llm_robot_task_planning robot_launch.py)", flush=True)
        return False

    def run_instruction(self, instruction: str):
        print(f"\n" + "="*50, flush=True)
        print(f" Instruction: '{instruction}'", flush=True)
        print(f"="*50, flush=True)

        # 1. Plan
        print(" Contacting LLM brain, please wait...", flush=True)
        plan = self.planner.generate_plan(instruction)
        print(f"\n [LLM Proposed Tool Calls JSON]:")
        print(json.dumps(plan, indent=2), flush=True)

        if not plan:
            print(f"\n [Planner]: No executable plan from the selected brain.", flush=True)
            print(f" The pinned brain (LLM_PROVIDER={self.planner.priority[0]}) could not "
                  f"produce a complete plan.", flush=True)
            print(f" No commands sent to robot. Check the brain/model/service and "
                  f"try the instruction again.\n", flush=True)
            return

        # 2. Validate
        valid, msg = self.validator.validate_plan(plan)
        print(f"\n [Safety Validator]: {' APPROVED' if valid else ' REJECTED'} - {msg}", flush=True)

        if not valid:
            print(f" Plan rejected safely. No commands sent to robot.\n", flush=True)
            return

        # 3. Execute with structured feedback and bounded recovery
        print(f"\n Executing Plan on Robot in Webots...", flush=True)
        self.recovery.reset()
        for step_idx, call in enumerate(plan):
            skill_name = call['skill']
            print(f" Step {step_idx+1}/{len(plan)}: {skill_name} {call['arguments']}", flush=True)

            result = self._execute_call(call)

            if result is not None:
                print(f" [Execution Feedback Result JSON]:")
                print(json.dumps(result, indent=2), flush=True)

            if result is not None and result.get("success"):
                print(f" [Recovery decision]: proceed (skill succeeded).", flush=True)
                continue

            reason = (result or {}).get("reason", "timeout (no result from navigation node within budget)")
            print(f" [Observed result]: step failed - reason='{reason}'.", flush=True)

            if self.recovery.should_retry(call, reason):
                print(f" [Recovery decision]: RETRY_ONCE - bounded retry of "
                      f"'{skill_name}' after timeout fault.", flush=True)
                result = self._execute_call(call)
                if result is not None:
                    print(f" [Retry Result JSON]:")
                    print(json.dumps(result, indent=2), flush=True)
                if result is not None and result.get("success"):
                    print(f" [Recovery outcome]: SUCCESS - robot recovered after 1 retry.", flush=True)
                    continue
                print(f" [Recovery outcome]: FAILED - target could not be reached "
                      f"even after retry. Stopping and reporting.", flush=True)
            else:
                print(f" [Recovery decision]: ABORT - fault is not retryable "
                      f"(validation/unknown-skill faults are never retried).", flush=True)
            print(f" Aborting remaining steps.\n", flush=True)
            break

        print(f"Task Execution Finished.\n", flush=True)

    def _execute_call(self, call: dict):
        """Publish one skill call and wait for its result.

        Returns the result dict, or None if the nav node is absent / silent.
        """
        skill_name = call.get('skill', '')

        # Check connection first, otherwise the command is silently lost
        if not self.wait_for_navigation(timeout_s=5.0):
            print(" ------------------------------------------------------------", flush=True)
            print(" WARNING: navigation node not connected.", flush=True)
            print(" Start Terminal 1 and leave it running:", flush=True)
            print("   ros2 launch llm_robot_task_planning robot_launch.py", flush=True)
            print(" (Webots + bridge + navigation). Returning to prompt.", flush=True)
            print(" ------------------------------------------------------------", flush=True)
            return None

        self.latest_result = None
        self.skill_pub.publish(String(data=json.dumps(call)))

        # Wait for the result, with deadline and heartbeats
        timeout_s = self.RESULT_TIMEOUT_S.get(skill_name, self.DEFAULT_TIMEOUT_S)
        deadline = time.time() + timeout_s
        next_heartbeat = time.time() + self.HEARTBEAT_S
        while self.latest_result is None and rclpy.ok() and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.latest_result is None and time.time() >= next_heartbeat:
                remaining = deadline - time.time()
                print(f"   ...robot is executing '{skill_name}' "
                      f"({remaining:.0f}s budget left), watch Webots...", flush=True)
                next_heartbeat = time.time() + self.HEARTBEAT_S

        if self.latest_result is None:
            print(" ------------------------------------------------------------", flush=True)
            print(f" WARNING: no result from the navigation node within {timeout_s:.0f}s.", flush=True)
            print(" Make sure Terminal 1 is running:", flush=True)
            print("   ros2 launch llm_robot_task_planning robot_launch.py", flush=True)
            print(" ------------------------------------------------------------", flush=True)
        return self.latest_result

def main(args=None):
    rclpy.init(args=args)
    node = TaskAgentNode()

    auto_tests = os.getenv("LLM_AUTO_TESTS", "0").strip() in ("1", "true", "True")

    nav_ready = node.wait_for_navigation(timeout_s=60.0)
    if not nav_ready:
        print(" WARNING: navigation node did not connect within 60s.", flush=True)
        print(" Commands will not move the robot until Terminal 1 is running:", flush=True)
        print("   ros2 launch llm_robot_task_planning robot_launch.py", flush=True)

    # ros2 launch does not forward keyboard input; require a ros2 run terminal
    if not auto_tests and not sys.stdin.isatty():
        print("\n" + "#"*60, flush=True)
        print(" ERROR: this node needs a keyboard terminal and cannot read", flush=True)
        print(" your input when started via 'ros2 launch'.", flush=True)
        print(" Start the interactive brain with 'ros2 run' instead:", flush=True)
        print("   LLM_PROVIDER=qwen   ros2 run llm_robot_task_planning task_agent_node", flush=True)
        print("   LLM_PROVIDER=ollama ros2 run llm_robot_task_planning task_agent_node", flush=True)
        print("   LLM_PROVIDER=mock   ros2 run llm_robot_task_planning task_agent_node", flush=True)
        print(" Keep 'ros2 launch llm_robot_task_planning robot_launch.py'", flush=True)
        print(" running in another terminal for Webots + navigation.", flush=True)
        print("#"*60, flush=True)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        sys.exit(1)

    # Batch mode: LLM_AUTO_TESTS=1 runs fixed test cases without a keyboard
    if auto_tests:
        test_cases = [
            "Go to storage.",
            "Visit storage, then workbench, and stop.",
            "Go to coordinate (5.0, 5.0)."
        ]
        for test in test_cases:
            node.run_instruction(test)
            time.sleep(1.0)

    print("\n" + "#"*60, flush=True)
    print(" Interactive Mode: Type a natural-language command.", flush=True)
    print("   examples: 'go to storage'", flush=True)
    print("             'visit storage then workbench and stop'", flush=True)
    print("             'go to coordinate 1.0 -0.5'", flush=True)
    print(" Type 'exit' to quit.", flush=True)
    print("#"*60, flush=True)

    try:
        while rclpy.ok():
            try:
                user_input = input("\nEnter Instruction > ").strip()
            except EOFError:
                break
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            if user_input:
                node.run_instruction(user_input)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
