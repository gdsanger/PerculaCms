"""Agent Registry – loads AgentDefinitions from ./agents/*.yml."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_registry: Optional[dict] = None


@dataclass
class AgentDefinition:
    """A single agent definition loaded from a YAML file."""

    agent_id: str
    name: str
    description: str
    provider: str
    model: str
    role: str
    task: str
    parameters: Optional[dict]


def _get_agents_dir() -> Path:
    """Return the resolved path to the agents directory from settings.BASE_DIR."""
    from django.conf import settings
    return Path(settings.BASE_DIR) / 'agents'


def _load_registry() -> dict:
    """Scan the agents directory for ``*.yml`` files and build the registry.

    Returns:
        Dict mapping ``agent_id`` (file stem) to :class:`AgentDefinition`.

    Raises:
        ValueError: If any agent file cannot be parsed or is missing required fields.
    """
    agents_dir = _get_agents_dir()
    agents: dict[str, AgentDefinition] = {}

    for path in sorted(agents_dir.glob('*.yml')):
        try:
            with path.open(encoding='utf-8') as fh:
                data = yaml.safe_load(fh)
        except Exception as exc:
            raise ValueError(f'Failed to parse agent file {path}: {exc}') from exc

        if not isinstance(data, dict):
            raise ValueError(
                f'Agent file {path} must be a YAML mapping, got {type(data).__name__}.'
            )

        agent_id = path.stem

        for required in ('role', 'task', 'provider', 'model'):
            if not data.get(required):
                raise ValueError(
                    f'Agent file {path}: missing required field "{required}".'
                )

        agents[agent_id] = AgentDefinition(
            agent_id=agent_id,
            name=data.get('name', agent_id),
            description=data.get('description', ''),
            provider=data['provider'],
            model=data['model'],
            role=data['role'],
            task=data['task'],
            parameters=data.get('parameters'),
        )

    logger.debug('Agent registry loaded: %d agent(s) from %s', len(agents), agents_dir)
    return agents


def get_registry() -> dict:
    """Return the singleton registry, loading it on first access."""
    global _registry
    if _registry is None:
        _registry = _load_registry()
    return _registry


def get_agent(agent_id: str) -> AgentDefinition:
    """Retrieve an :class:`AgentDefinition` by its ID.

    Args:
        agent_id: The ID of the agent (file stem, e.g. ``'text-optimization-agent'``).

    Returns:
        The matching :class:`AgentDefinition`.

    Raises:
        KeyError: If no agent with the given ID is registered.
    """
    registry = get_registry()
    if agent_id not in registry:
        raise KeyError(
            f'Agent "{agent_id}" not found. Available agents: {sorted(registry.keys())}'
        )
    return registry[agent_id]
