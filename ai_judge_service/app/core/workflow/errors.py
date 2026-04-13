from __future__ import annotations


class WorkflowTransitionError(RuntimeError):
    def __init__(self, *, job_id: int, from_status: str, to_status: str) -> None:
        super().__init__(f"invalid workflow transition for job={job_id}: {from_status}->{to_status}")
        self.job_id = job_id
        self.from_status = from_status
        self.to_status = to_status
