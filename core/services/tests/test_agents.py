"""Tests for the agent service."""

from django.test import TestCase
from pathlib import Path

from core.services.agents.registry import AgentRegistry, get_agent, AgentNotFoundError
from core.services.agents.yaml_parser import parse_agent_yaml, AgentParseError


class AgentRegistryTest(TestCase):
    """Tests for agent registry."""

    def test_load_text_optimization_agent(self):
        """Test that text-optimization-agent can be loaded."""
        agent = get_agent('text-optimization-agent')
        self.assertEqual(agent.agent_id, 'text-optimization-agent')
        self.assertEqual(agent.name, 'text-optimization-agent')
        self.assertEqual(agent.provider, 'OpenAI')
        self.assertEqual(agent.model, 'gpt-4.1')
        self.assertIsNotNone(agent.role)
        self.assertIsNotNone(agent.task)

    def test_load_content_html_layout_agent(self):
        """Test that content-html-layout-agent can be loaded."""
        agent = get_agent('content-html-layout-agent')
        self.assertEqual(agent.agent_id, 'content-html-layout-agent')
        self.assertEqual(agent.provider, 'OpenAI')
        self.assertIsNotNone(agent.role)
        self.assertIsNotNone(agent.task)

    def test_agent_not_found(self):
        """Test that AgentNotFoundError is raised for non-existent agent."""
        with self.assertRaises(AgentNotFoundError):
            get_agent('non-existent-agent')

    def test_parse_yaml_file(self):
        """Test parsing a YAML agent file directly."""
        from django.conf import settings
        agent_file = settings.BASE_DIR / 'agents' / 'text-optimization-agent.yml'
        agent = parse_agent_yaml(agent_file)
        self.assertEqual(agent.agent_id, 'text-optimization-agent')
        self.assertIn('Textoptimierungsagent', agent.role)
