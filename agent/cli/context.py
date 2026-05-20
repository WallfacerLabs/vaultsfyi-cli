"""Shared CLI runtime context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent import Agent
from agent.cli import config as config_mod
from agent.cli.output import OutputFormat
from agent.decision import apply_preference


@dataclass
class CliContext:
    output: OutputFormat
    config_path: Path | None
    agent_name: str | None
    cfg: dict

    def agent(self) -> Agent:
        with config_mod.exported_env(self.cfg):
            return Agent(config=config_mod.agent_config(self.cfg))

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
