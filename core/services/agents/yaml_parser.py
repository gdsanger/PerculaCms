"""YAML parser for agent definitions."""

import yaml
from pathlib import Path
from typing import Any

from .models import AgentDefinition


class AgentParseError(Exception):
    """Raised when an agent YAML file cannot be parsed."""

    def __init__(self, message: str, file_path: Path):
        self.file_path = file_path
        super().__init__(f"{message} (file: {file_path})")


def parse_agent_yaml(file_path: Path) -> AgentDefinition:
    """Parse a YAML agent definition file.

    Args:
        file_path: Path to the YAML file.

    Returns:
        AgentDefinition instance.

    Raises:
        AgentParseError: If the file cannot be parsed or required fields are missing.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise AgentParseError(f"File not found", file_path)
    except yaml.YAMLError as e:
        raise AgentParseError(f"Invalid YAML syntax: {e}", file_path)
    except Exception as e:
        raise AgentParseError(f"Failed to read file: {e}", file_path)

    if not isinstance(data, dict):
        raise AgentParseError("YAML root must be a dictionary", file_path)

    # Validate required fields
    required_fields = ['name', 'description', 'provider', 'model', 'role', 'task']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise AgentParseError(
            f"Missing required fields: {', '.join(missing_fields)}",
            file_path
        )

    # Extract agent_id from filename (stem without extension)
    agent_id = file_path.stem

    try:
        return AgentDefinition(
            agent_id=agent_id,
            name=data['name'],
            description=data['description'],
            provider=data['provider'],
            model=data['model'],
            role=data['role'],
            task=data['task'],
            parameters=data.get('parameters'),
            cache=data.get('cache'),
        )
    except Exception as e:
        raise AgentParseError(f"Failed to construct AgentDefinition: {e}", file_path)
