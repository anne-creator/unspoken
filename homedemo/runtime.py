"""Composition root: one bus, the simulated home, the agents, the deciders and the scenario runner.

Implements contracts.RuntimeAPI for the web UI. Order of bus subscriptions matters for reset():
the sim and the UI subscribe first, the agents last, so reset can drop and rebuild only the agents
(fresh perception memory, policy caches and open asks) while the UI stream keeps running.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, fields
from typing import Any

from .agents import start_agents
from .agents.house_agent import HouseAgent
from .bus import Bus
from .contracts import AGENTS, Event, Settings, T
from .decider_client import Decider, FakeDecider, HttpDecider
from .sim import World, load_home

log = logging.getLogger("homedemo.runtime")

WORLD_STEPS = {"set_time", "move", "activity", "idle", "say", "tv_say", "outside_say", "set_env",
               "set_device", "phone", "leave", "arrive"}


DECIDER_SETTINGS = {"decider_2b_url", "decider_12b_url", "bedrock_model_id", "bedrock_region", "bedrock_profile"}

# What the intent / scene decider agents do, by settings.escalate_to (shown in the UI's agent graph).
BLURBS: dict[str, dict[str, str]] = {
    "bedrock": {
        "scene_decider": "Asks the Decider 2B what the house should do about what it sees; Claude on Bedrock "
                         "decides when the 2B is unsure.",
        "intent_decider": "Asks the Decider 2B which tool the speaker wants, with no wake word. Claude on Bedrock "
                          "only if unsure.",
    },
    "12b": {
        "scene_decider": "Asks the Decider 2B what the house should do about what it sees; the 12B decides when "
                         "the 2B is unsure.",
        "intent_decider": "Asks the Decider 2B which tool the speaker wants, with no wake word. The 12B only if "
                          "unsure.",
    },
}


def build_deciders(settings: Settings) -> dict[str, Any]:
    """The decider slots: the 2B and 12B servers, the FakeDecider, and the Strands house agent ("bedrock",
    Claude on Bedrock behind the DeciderToolRouter; its model is built lazily on first use)."""
    deciders = {"2b": HttpDecider("decider-2b", settings.decider_2b_url),
            "fake": FakeDecider(),
            "bedrock": HouseAgent(settings)}
    allowed = os.getenv("HOMEDEMO_ALLOWED_MODES", "2b,12b,cascade,fake").split(",")
    escalations = os.getenv("HOMEDEMO_ALLOWED_ESCALATIONS", "bedrock,12b").split(",")
    if "12b" in allowed or "12b" in escalations:
        deciders["12b"] = HttpDecider("decider-12b", settings.decider_12b_url)
    return deciders


class Runtime:
    def __init__(self, settings: Settings | None = None, *, deciders: dict[str, Any] | None = None,
                 seed: int = 7, noise: float = 0.3, trace_path: str | None = None,
                 tick_seconds: float = 1.0) -> None:
        self.settings = settings or Settings()
        self.home = load_home()
        self.bus = Bus(trace_path=trace_path)
        self.world = World(self.home, self.bus, self.settings, seed=seed, noise=noise)
        self.deciders = deciders or build_deciders(self.settings)
        self.agents: list = []
        self._agent_sub_index = 0
        self._tick_seconds = tick_seconds
        self._tick_task: asyncio.Task | None = None
        self._scenario_task: asyncio.Task | None = None
        self._runner = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ lifecycle
    async def start(self, *, ticking: bool = True) -> None:
        from .scenarios import ScenarioRunner  # imported late: optional during unit tests

        await self.world.start()
        self._runner = ScenarioRunner(self.bus, self.world, self.settings, self.home, reset_before_run=False)
        self._start_agents()
        await self.bus.drain(60)
        if ticking and self._tick_seconds > 0:
            self._tick_task = asyncio.create_task(self._tick_loop(), name="runtime.tick")

    def _start_agents(self) -> None:
        self._agent_sub_index = self.bus.subscription_count()
        self.agents = start_agents(self.bus, self.home, self.settings, self.deciders)

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self._tick_seconds)
            if self._lock.locked():
                continue
            try:
                await self.world.tick(self._tick_seconds * self.settings.speed)
            except Exception:  # physics must never kill the house
                log.exception("tick failed")

    async def close(self) -> None:
        await self.stop_scenario()
        if self._tick_task:
            self._tick_task.cancel()
        await self.bus.cancel_pending()
        for d in self.deciders.values():
            if hasattr(d, "aclose"):
                await d.aclose()

    # ------------------------------------------------------------------ RuntimeAPI
    def snapshot(self) -> dict[str, Any]:
        return self.world.snapshot()

    def agent_graph(self) -> list[dict[str, Any]]:
        busy = {a.name: bool(getattr(a, "busy", False)) for a in self.agents}
        blurbs = BLURBS.get(self.settings.escalate_to, {}) if self.settings.decider_mode == "cascade" else {}
        return [{**a, "blurb": blurbs.get(a["name"], a["blurb"]), "busy": busy.get(a["name"], False)} for a in AGENTS]

    def scenarios(self) -> list[dict[str, Any]]:
        from .scenarios import load_scenarios

        return [{"id": s["id"], "title": s["title"], "blurb": s.get("blurb", ""), "tags": s.get("tags", []),
                 "steps": len(s.get("steps", []))} for s in load_scenarios()]

    async def run_scenario(self, scenario_id: str) -> None:
        from .scenarios import get

        scenario = get(scenario_id)
        if scenario is None:
            raise KeyError(scenario_id)
        await self.reset()
        self._scenario_task = asyncio.create_task(self._runner.run(scenario), name=f"scenario:{scenario_id}")

    async def stop_scenario(self) -> None:
        if self._runner is not None and self._scenario_task and not self._scenario_task.done():
            await self._runner.stop()
            self._scenario_task.cancel()
            await asyncio.gather(self._scenario_task, return_exceptions=True)
        self._scenario_task = None

    async def reset(self) -> None:
        async with self._lock:
            await self.stop_scenario()
            await self.bus.cancel_pending()
            self.bus.unsubscribe_from(self._agent_sub_index)
            self._start_agents()
            await self.world.reset()
            await self.bus.drain(60)
            await self.bus.publish(Event(T.LOG, {"agent": "runtime", "level": "info", "text": "House reset."},
                                         source="runtime", ts=self.world.clock))

    async def step(self, step: dict[str, Any]) -> None:
        if step.get("do") not in WORLD_STEPS:
            raise ValueError(f"not a world step: {step.get('do')!r}")
        await self.world.step(step)

    async def phone_reply(self, request_id: str, answer: str) -> None:
        await self.bus.publish(Event(T.REPLY, {"request_id": request_id, "answer": answer, "by": "web"},
                                     source="phone", ts=self.world.clock))

    async def update_settings(self, **changes: Any) -> Settings:
        known = {f.name for f in fields(Settings)}
        bad = set(changes) - known
        if bad:
            raise ValueError(f"unknown settings: {sorted(bad)}")
        for k, v in changes.items():
            setattr(self.settings, k, v)
        if DECIDER_SETTINGS & set(changes):
            self.deciders.update(build_deciders(self.settings))
        await self.bus.publish(Event(T.LOG, {"agent": "runtime", "level": "info",
                                             "text": f"Settings changed: {changes}"},
                                     source="runtime", ts=self.world.clock))
        return self.settings

    def settings_dict(self) -> dict[str, Any]:
        return asdict(self.settings)
