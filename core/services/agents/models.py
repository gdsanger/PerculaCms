"""Data models for agent definitions."""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class AgentDefinition:
    """Represents a loaded agent definition from YAML."""

    agent_id: str
    name: str
    description: str
    provider: str
    model: str
    role: str  # System message
    task: str  # User instruction template
    parameters: Optional[dict[str, Any]] = None
    cache: Optional[dict[str, Any]] = None

    @property
    def system_message(self) -> str:
        """Return the system message for this agent."""
        return self.role

    @property
    def task_instruction(self) -> str:
        """Return the task instruction for this agent."""
        return self.task
