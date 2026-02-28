"""AgentService – execute registered agents via the AI Router."""

import logging
from dataclasses import dataclass
from typing import Any, Optional, Union

from .registry import get_agent
from ..ai.router import AIRouter

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    """Result returned from a single agent run."""

    agent_id: str
    output_text: Optional[str]
    output_json: Optional[Union[dict, list]]
    raw: Any
    provider: Optional[str]
    model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]


def run_agent(
    agent_id: str,
    *,
    task_input: Union[dict, str],
    user=None,
    client_ip: Optional[str] = None,
    context: Optional[dict] = None,
) -> AgentRunResult:
    """Execute a registered agent with the given input via the AI Router.

    Args:
        agent_id: ID of the agent to run (file stem from ``agents/*.yml``).
        task_input: Text or dict to pass as the user message.
        user: Django ``User`` instance for audit logging.
        client_ip: Caller IP address for audit logging.
        context: Optional extra context (reserved for future use).

    Returns:
        :class:`AgentRunResult` with ``output_text`` populated.

    Raises:
        KeyError: If the agent is not found in the registry.
        :class:`~core.services.base.ServiceNotConfigured`: If no AI model is configured.
    """
    agent = get_agent(agent_id)

    if isinstance(task_input, dict):
        input_str = '\n'.join(f'{k}: {v}' for k, v in task_input.items())
    else:
        input_str = str(task_input)

    messages = [
        {'role': 'system', 'content': f'{agent.role}\n\n{agent.task}'},
        {'role': 'user', 'content': input_str},
    ]

    router = AIRouter()
    response = router.chat(
        messages=messages,
        model_id=agent.model,
        provider_type=agent.provider,
        user=user,
        client_ip=client_ip,
        agent=agent_id,
    )

    return AgentRunResult(
        agent_id=agent_id,
        output_text=response.text,
        output_json=None,
        raw=response.raw,
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
