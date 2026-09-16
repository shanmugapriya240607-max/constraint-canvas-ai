"""Shared response contracts using Pydantic v2."""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    status: Literal["ok", "error"]
    message: str


class RootResponse(MessageResponse):
    version: str
    docs: str
    health: str


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    service: str
    version: str
    database: Literal["connected", "disconnected"]
