"""Agent registry for loading and accessing YAML-defined agents."""

import logging
from pathlib import Path
from typing import Optional

from django.conf import settings

from .models import AgentDefinition
from .yaml_parser import parse_agent_yaml, AgentParseError

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when a requested agent cannot be found."""
    pass


class AgentRegistry:
    """Registry for loading and accessing YAML-defined agents.

    Loads agents lazily on first access from ./agents/*.yml
    """

    _instance: Optional['AgentRegistry'] = None
    _agents: dict[str, AgentDefinition] = {}
    _loaded: bool = False

    def __new__(cls):
        """Singleton pattern to ensure only one registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_agent(self, agent_id: str) -> AgentDefinition:
        """Get an agent by ID.

        Args:
            agent_id: The agent identifier (YAML filename without extension).

        Returns:
            AgentDefinition instance.

        Raises:
            AgentNotFoundError: If the agent cannot be found.
        """
        if not self._loaded:
            self._load_agents()

        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")

        return agent

    def list_agents(self) -> list[str]:
        """List all available agent IDs.

        Returns:
            List of agent IDs.
        """
        if not self._loaded:
            self._load_agents()

        return list(self._agents.keys())

    def _load_agents(self):
        """Load all agents from the ./agents directory."""
        if self._loaded:
            return

        agents_dir = settings.BASE_DIR / 'agents'
        if not agents_dir.exists():
            logger.warning(f"Agents directory not found: {agents_dir}")
            self._loaded = True
            return

        # Find all .yml and .yaml files, sort for deterministic loading
        yaml_files = sorted(agents_dir.glob('*.yml')) + sorted(agents_dir.glob('*.yaml'))

        loaded_count = 0
        for yaml_file in yaml_files:
            try:
                agent = parse_agent_yaml(yaml_file)
                self._agents[agent.agent_id] = agent
                loaded_count += 1
                logger.debug(f"Loaded agent: {agent.agent_id} from {yaml_file.name}")
            except AgentParseError as e:
                # Re-raise parse errors to fail fast
                logger.error(f"Failed to parse agent file: {e}")
                raise

        logger.info(f"Loaded {loaded_count} agents from {agents_dir}")
        self._loaded = True

    def reload(self):
        """Force reload of all agents from disk."""
        self._agents.clear()
        self._loaded = False
        self._load_agents()


# Singleton instance
_registry = AgentRegistry()


def get_agent(agent_id: str) -> AgentDefinition:
    """Get an agent by ID from the singleton registry.

    Args:
        agent_id: The agent identifier.

    Returns:
        AgentDefinition instance.

    Raises:
        AgentNotFoundError: If the agent cannot be found.
    """
    return _registry.get_agent(agent_id)


def list_agents() -> list[str]:
    """List all available agent IDs.

    Returns:
        List of agent IDs.
    """
    return _registry.list_agents()
