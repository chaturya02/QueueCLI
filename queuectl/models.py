"""Job models and data structures"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
import json


class JobState(str, Enum):
    """Job state enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class Job:
    """Represents a background job"""

    def __init__(
        self,
        id: str,
        command: str,
        state: JobState = JobState.PENDING,
        attempts: int = 0,
        max_retries: int = 3,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        next_retry_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ):
        self.id = id
        self.command = command
        self.state = state if isinstance(state, JobState) else JobState(state)
        self.attempts = attempts
        self.max_retries = max_retries
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.next_retry_at = next_retry_at
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            "id": self.id,
            "command": self.command,
            "state": self.state.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        """Convert job to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary"""
        # Parse datetime fields
        created_at = None
        if data.get("created_at"):
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            else:
                created_at = data["created_at"]

        updated_at = None
        if data.get("updated_at"):
            if isinstance(data["updated_at"], str):
                updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            else:
                updated_at = data["updated_at"]

        next_retry_at = None
        if data.get("next_retry_at"):
            if isinstance(data["next_retry_at"], str):
                next_retry_at = datetime.fromisoformat(data["next_retry_at"].replace("Z", "+00:00"))
            else:
                next_retry_at = data["next_retry_at"]

        return cls(
            id=data["id"],
            command=data["command"],
            state=data.get("state", JobState.PENDING),
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            created_at=created_at,
            updated_at=updated_at,
            next_retry_at=next_retry_at,
            error_message=data.get("error_message"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Job":
        """Create job from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return f"Job(id={self.id}, state={self.state.value}, attempts={self.attempts})"
