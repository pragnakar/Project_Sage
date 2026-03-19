"""Pydantic models for the example app."""

from pydantic import BaseModel


class EchoResult(BaseModel):
    """Result of the echo_tool."""
    message: str
    echo: str
