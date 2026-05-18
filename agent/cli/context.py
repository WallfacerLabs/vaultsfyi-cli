"""Shared CLI runtime context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent import Agent
from agent.cli import config as config_mod
from agent.cli.output import OutputFormat


@dataclass
class CliContext:
    output: OutputFormat
    config_path: Path | None
    cfg: dict

    def agent(self) -> Agent:
        config_mod.export_env(self.cfg)
        return Agent(config=config_mod.agent_config(self.cfg))


def build_context(output: OutputFormat, config_path: Path | None) -> CliContext:
    cfg = config_mod.load_config(config_path)
    return CliContext(output=output, config_path=config_path, cfg=cfg)
