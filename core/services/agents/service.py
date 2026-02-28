"""Agent service for executing AI agents."""

import logging
from dataclasses import dataclass
from typing import Optional, Any, Union

from core.services.ai.router import AIRouter
from core.services.ai.schemas import AIResponse

from .registry import get_agent, AgentNotFoundError
from .models import AgentDefinition

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    """Result of running an agent.

    Attributes:
        agent_id: The agent identifier.
        output_text: Plaintext output from the agent (if applicable).
        output_json: JSON output from the agent (if applicable).
        raw: Raw response from the provider.
        provider: Provider type used.
        model: Model ID used.
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
    """

    agent_id: str
    output_text: Optional[str] = None
    output_json: Optional[Union[dict, list]] = None
    raw: Any = None
    provider: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class AgentService:
    """Service for running AI agents."""

    def __init__(self, router: Optional[AIRouter] = None):
        """Initialize the agent service.

        Args:
            router: Optional AIRouter instance. If not provided, a new one will be created.
        """
        self.router = router or AIRouter()

    def run_agent(
        self,
        agent_id: str,
        *,
        task_input: Union[dict, str],
        user=None,
        client_ip: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentRunResult:
        """Run an agent with the given input.

        Args:
            agent_id: The agent identifier.
            task_input: Input for the agent (string or dict).
            user: Optional Django User instance for audit logging.
            client_ip: Optional client IP address for audit logging.
            context: Optional context dictionary (not used currently, reserved for future).

        Returns:
            AgentRunResult with output and metadata.

        Raises:
            AgentNotFoundError: If the agent cannot be found.
            Exception: If the agent execution fails.
        """
        # Get agent definition
        try:
            agent = get_agent(agent_id)
        except AgentNotFoundError:
            logger.error(f"Agent not found: {agent_id}")
            raise

        # Build messages for the AI router
        messages = self._build_messages(agent, task_input, context)

        # Execute via AI router
        try:
            ai_response = self.router.chat(
                messages=messages,
                provider_type=agent.provider,
                model_id=agent.model,
                user=user,
                client_ip=client_ip,
                agent=agent_id,  # This will be logged in AIJobsHistory
            )
        except Exception as e:
            logger.error(f"Agent execution failed for {agent_id}: {e}")
            raise

        # Build result
        result = AgentRunResult(
            agent_id=agent_id,
            output_text=ai_response.text.strip() if ai_response.text else None,
            output_json=None,  # Not parsing JSON for text-optimization-agent
            raw=ai_response.raw,
            provider=ai_response.provider,
            model=ai_response.model,
            input_tokens=ai_response.input_tokens,
            output_tokens=ai_response.output_tokens,
        )

        logger.info(
            f"Agent {agent_id} executed successfully: "
            f"{result.input_tokens} input tokens, {result.output_tokens} output tokens"
        )

        return result

    def _build_messages(
        self,
        agent: AgentDefinition,
        task_input: Union[dict, str],
        context: Optional[dict] = None,
    ) -> list[dict]:
        """Build messages for the AI router from agent definition and input.

        Args:
            agent: Agent definition.
            task_input: Input for the agent.
            context: Optional context dictionary.

        Returns:
            List of messages in OpenAI format.
        """
        messages = []

        # Add system message (role)
        if agent.system_message:
            messages.append({
                'role': 'system',
                'content': agent.system_message,
            })

        # Build user message
        # For text-optimization-agent, task_input is the text to optimize
        # The task instruction describes what to do
        user_content = self._format_user_message(agent, task_input, context)
        messages.append({
            'role': 'user',
            'content': user_content,
        })

        return messages

    def _format_user_message(
        self,
        agent: AgentDefinition,
        task_input: Union[dict, str],
        context: Optional[dict] = None,
    ) -> str:
        """Format the user message content.

        Args:
            agent: Agent definition.
            task_input: Input for the agent.
            context: Optional context dictionary.

        Returns:
            Formatted user message content.
        """
        # Start with the task instruction
        parts = [agent.task_instruction]

        # Add context if provided (for future extensibility)
        if context:
            context_str = '\n'.join([f"{k}: {v}" for k, v in context.items()])
            parts.append(f"\nContext:\n{context_str}")

        # Add the actual input
        if isinstance(task_input, str):
            parts.append(f"\nInput:\n{task_input}")
        else:
            # If dict, convert to string representation
            input_str = '\n'.join([f"{k}: {v}" for k, v in task_input.items()])
            parts.append(f"\nInput:\n{input_str}")

        return '\n'.join(parts)


# Convenience function for direct usage
def run_agent(
    agent_id: str,
    *,
    task_input: Union[dict, str],
    user=None,
    client_ip: Optional[str] = None,
    context: Optional[dict] = None,
) -> AgentRunResult:
    """Run an agent with the given input.

    Convenience function that creates an AgentService instance and runs the agent.

    Args:
        agent_id: The agent identifier.
        task_input: Input for the agent (string or dict).
        user: Optional Django User instance for audit logging.
        client_ip: Optional client IP address for audit logging.
        context: Optional context dictionary.

    Returns:
        AgentRunResult with output and metadata.

    Raises:
        AgentNotFoundError: If the agent cannot be found.
        Exception: If the agent execution fails.
    """
    service = AgentService()
    return service.run_agent(
        agent_id,
        task_input=task_input,
        user=user,
        client_ip=client_ip,
        context=context,
    )
