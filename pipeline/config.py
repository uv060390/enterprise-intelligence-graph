"""Runtime configuration. Everything overridable via environment variables."""

import os

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "eigraphdev")  # dev-only default

MOCKS_URL = os.environ.get("MOCKS_URL", "http://localhost:8010")

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
