"""Shared CLI runtime context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent import Agent
from agent.api.v2 import VaultsApiClient
from agent.cli import config as config_mod
from agent.cli.output import OutputFormat
from agent.decision import apply_preference


_CURRENT_CONTEXT: "CliContext | None" = None


@dataclass
class ContextApiClient:
    cfg: dict

    def request(self, endpoint: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        with config_mod.exported_env(self.cfg):
            client = VaultsApiClient(base_url=self.cfg["vaults"].get("api_url", "https://api.vaults.fyi"))
            return client.request(endpoint, params=params, timeout=timeout)


@dataclass
class CliContext:
    output: OutputFormat
    config_path: Path | None
    agent_name: str | None
    cfg: dict

    def agent(self) -> Agent:
        with config_mod.exported_env(self.cfg):
            return Agent(config=config_mod.agent_config(self.cfg))

    def api_client(self) -> ContextApiClient:
        return ContextApiClient(self.cfg)

    def with_preference(self, preference_name: str | None) -> "CliContext":
        if not preference_name:
            return self
        cfg = apply_preference(self.cfg, preference_name)
        return CliContext(output=self.output, config_path=self.config_path, agent_name=self.agent_name, cfg=cfg)

    @property
    def effective_agent_name(self) -> str:
        return self.cfg.get("agent", {}).get("name") or self.agent_name or "default"


def build_context(output: OutputFormat, config_path: Path | None, agent_name: str | None = None) -> CliContext:
    cfg = config_mod.load_config(config_path, agent_name)
    return CliContext(output=output, config_path=config_path, agent_name=agent_name, cfg=cfg)


def set_current_context(ctx: CliContext) -> None:
    global _CURRENT_CONTEXT
    _CURRENT_CONTEXT = ctx


def current_context() -> CliContext | None:
    return _CURRENT_CONTEXT
