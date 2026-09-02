class RecoveryHandler:
    """Handles failure feedback and bounded recovery policies."""
    def __init__(self, max_retries=1):
        self.max_retries = max_retries
        self.retry_counts = {}

    def should_retry(self, skill_call: dict, reason: str) -> bool:
        skill = skill_call.get("skill")
        count = self.retry_counts.get(skill, 0)
        if reason == "timeout" and count < self.max_retries:
            self.retry_counts[skill] = count + 1
            return True
        return False
