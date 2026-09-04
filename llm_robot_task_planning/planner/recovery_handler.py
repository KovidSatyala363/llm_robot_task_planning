class RecoveryHandler:
    """Bounded recovery: retry the same call once on timeout; abort otherwise."""

    RETRYABLE_REASONS = ("timeout",)  # substring matched against the result reason

    def __init__(self, max_retries=1):
        self.max_retries = max_retries
        self.retry_counts = {}

    def is_retryable(self, reason: str) -> bool:
        reason = (reason or "").lower()
        return any(token in reason for token in self.RETRYABLE_REASONS)

    def should_retry(self, skill_call: dict, reason: str) -> bool:
        skill = skill_call.get("skill")
        count = self.retry_counts.get(skill, 0)
        if self.is_retryable(reason) and count < self.max_retries:
            self.retry_counts[skill] = count + 1
            return True
        return False

    def reset(self):
        """Clear retry counters (called at the start of each new instruction)."""
        self.retry_counts.clear()
