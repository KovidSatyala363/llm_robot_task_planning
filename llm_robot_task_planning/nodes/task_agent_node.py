import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
import time
from ament_index_python.packages import get_package_share_directory
from llm_robot_task_planning.planner.llm_planner import LLMTaskPlanner
from llm_robot_task_planning.planner.plan_validator import PlanValidator

class TaskAgentNode(Node):
    def __init__(self):
        super().__init__('task_agent_node')

        try:
            pkg_dir = get_package_share_directory('llm_robot_task_planning')
            loc_path = os.path.join(pkg_dir, 'config', 'locations.yaml')
        except Exception:
            loc_path = os.path.expanduser('~/ros2_ws/src/llm_robot_task_planning/config/locations.yaml')

        self.planner = LLMTaskPlanner(loc_path)
        self.validator = PlanValidator()

        self.skill_pub = self.create_publisher(String, '/agent0/execute_skill', 10)
        self.result_sub = self.create_subscription(String, '/agent0/skill_result', self.result_callback, 10)
        self.latest_result = None
        self.get_logger().info("Task Agent initialized.")

    def result_callback(self, msg: String):
        self.latest_result = json.loads(msg.data)

    def run_instruction(self, instruction: str):
        print(f"\n" + "="*50)
        print(f" Instruction: '{instruction}'")
        print(f"="*50)

        # 1. LLM Tool Calling
        plan = self.planner.generate_plan(instruction)
        print(f"\n [LLM Proposed Tool Calls JSON]:")
        print(json.dumps(plan, indent=2))

        # 2. Safety Validation
        valid, msg = self.validator.validate_plan(plan)
        print(f"\n [Safety Validator]: {' APPROVED' if valid else ' REJECTED'} - {msg}")

        if not valid:
            print(f" Plan rejected safely. No commands sent to robot.\n")
            return

        # 3. Execution on Webots Robot
        print(f"\n Executing Plan on Robot in Webots...")
        for step_idx, call in enumerate(plan):
            print(f" Step {step_idx+1}/{len(plan)}: {call['skill']} {call['arguments']}")
            self.latest_result = None
            self.skill_pub.publish(String(data=json.dumps(call)))

            # Wait for skill result from Navigation Node
            while self.latest_result is None and rclpy.ok():
                rclpy.spin_once(self, timeout_sec=0.05)

            print(f" [Execution Feedback Result JSON]:")
            print(json.dumps(self.latest_result, indent=2))

            if not self.latest_result.get("success"):
                print(f"Step failed ({self.latest_result.get('reason')}). Aborting remaining steps.")
                break

        print(f"Task Execution Finished.\n")

def main(args=None):
    rclpy.init(args=args)
    node = TaskAgentNode()

    # The 3 Mandatory Test Cases from Assignment
    test_cases = [
        "Go to storage.",
        "Visit storage, then workbench, and stop.",
        "Go to coordinate (5.0, 5.0)."
    ]

    for test in test_cases:
        node.run_instruction(test)
        time.sleep(1.0)

    # Interactive Mode
    print("\n" + "#"*60)
    print("Interactive Mode: Type any command (or 'exit' to quit):")
    print("#"*60)

    try:
        while rclpy.ok():
            user_input = input("\nEnter Instruction > ").strip()
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            if user_input:
                node.run_instruction(user_input)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()