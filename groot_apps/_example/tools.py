"""Example app tools."""

from groot.artifact_store import ArtifactStore
from groot_apps._example.models import EchoResult


async def echo_tool(store: ArtifactStore, message: str) -> EchoResult:
    """Echo a message back. Demonstrates the minimal tool pattern."""
    return EchoResult(message=message, echo=f"Echo: {message}")
