import time
import datetime
import logging
import warnings
import numpy as np
from typing import Any
from pydantic import BaseModel, Field, model_validator

from agents.agents import AgentType
from runner.state import AgentState, initialise_population
from runner.soa import to_soa
from runner.simulationConfig import SimulationConfig
from topology.topology import build_topologies, TopologyProtocol
from behaviour.executor import compile_behaviours, run_step, CompiledEntry
from behaviour.model import SimulationModel
from scheduler.scheduler import compile_scheduling, ScheduleConfig
from stopping.engine import StoppingConfig, StopResult

def _build_population_for_type(
    agent_type: AgentType,
    overrides: list[dict[str, Any]],
    rng: np.random.Generator,
) -> list[AgentState]:
    kept = overrides[: agent_type.count]
    if len(overrides) > agent_type.count:
        warnings.warn(
            f"agent type '{agent_type.name}': {len(overrides)} rows supplied, "
            f"only {agent_type.count} expected — ignoring the extra "
            f"{len(overrides) - agent_type.count}."
        )
    explicit = [AgentState(agent_type_name=agent_type.name, state=row) for row in kept]

    remainder = agent_type.count - len(kept)
    if overrides and remainder > 0:
        warnings.warn(
            f"agent type '{agent_type.name}': only {len(kept)} of "
            f"{agent_type.count} agents supplied — generating the "
            f"remaining {remainder} normally."
        )
    generated = initialise_population(agent_type.model_copy(update={"count": remainder}), rng) if remainder else []

    return explicit + generated

class Simulation():
    def __init__(
        self,
        live_population: dict[str, AgentState],
        compiled_behaviours: dict[str, list[CompiledEntry]],
        topologies: dict[str, TopologyProtocol],
        model: SimulationModel,
        schedule: ScheduleConfig,
        agent_types: dict[str, AgentType],
        stopping_config: StoppingConfig,
    ):
        """
        Args:
            live_population: agent_id -> AgentState, the mutable population
                this simulation will step forward each call to __call__.
            compiled_behaviours: output of compile_behaviours — agent type
                name -> ordered list of compiled behaviour/expression entries.
            topologies: named topology instances from build_topologies.
            model: the persistent SimulationModel shared across all steps.
            schedule: compiled ScheduleConfig controlling turn order/quota.
            agent_types: agent type name -> AgentType, needed by lifecycle
                events (reproduce/external_entry) for fresh-attribute sampling.
            stopping_config: compiled StoppingConfig — max_steps and any
                condition expressions that end the run early.
        """
        self.live_population = live_population
        self.compiled_behaviours = compiled_behaviours
        self.topologies = topologies
        self.model = model
        self.schedule = schedule
        self.agent_types = agent_types
        self.stopping_config = stopping_config
        self.step_number = 0
        self._config: SimulationConfig | None = None  # set by from_config()

        self.logger = logging.getLogger('simulator')

    def __call__(self) -> StopResult:
        """Run the simulation to completion.

        Repeatedly calls run_step, incrementing step_number each time,
        until run_step's returned StopResult indicates the simulation
        should stop (max_steps reached, a condition was met, or an error
        occurred during condition evaluation — see stopping/engine.py).

        Returns:
            The final StopResult that ended the run.
        """
        start_time = datetime.datetime.now()
        filename = self.params['name'] if self.params['name'] != "" else ""
        '''
        Simulation starts here
        '''
        self.logger.info("Simulation start.")
        self.logger.info(
            f"agent_types={list(self.agent_types.keys())}, "
            f"population={len(self.live_population)}"
        )

        result = StopResult(False)
        while not result.stopped:
            self.step_number += 1
            self.logger.info(f"Simulation step: {self.step_number}")
            result = run_step(
                live_population=self.live_population,
                compiled_behaviours=self.compiled_behaviours,
                topologies=self.topologies,
                model=self.model,
                schedule=self.schedule,
                agent_types=self.agent_types,
                step_number=self.step_number,
                stopping_config=self.stopping_config,
            )
            time.sleep(1)  # todo: Find out why at the simulation code side there must be a time sleep as well

        if filename != "":
            self.logger.info(f"Log file printed in {filename}.txt")
        self.logger.info(f"Simulation finished in {datetime.datetime.now() - start_time}. ")
        self.logger.info(
            f"Simulation finished at step {self.step_number}: "
            f"reason={result.reason}, detail={result.detail}"
        )
        return result

    @classmethod
    def from_config(cls, config: dict) -> "Simulation":
        cfg = SimulationConfig.model_validate(config)
        rng = np.random.default_rng(cfg.seed)

        agent_types = {at.name: at for at in cfg.agent_types}
        live_population: dict[str, AgentState] = {}
        for name, agent_type in agent_types.items():
            for agent in _build_population_for_type(agent_type, cfg.initial_population.get(name, []), rng):
                live_population[agent.agent_id] = agent

        soa = to_soa(list(live_population.values()))
        dumped = cfg.model_dump()

        topologies = build_topologies(dumped, soa, rng=rng)
        compiled_behaviours = compile_behaviours(dumped, topologies)
        schedule = compile_scheduling(dumped)
        model = SimulationModel(params={}, rng=rng)

        sim = cls(
            live_population=live_population,
            compiled_behaviours=compiled_behaviours,
            topologies=topologies,
            model=model,
            schedule=schedule,
            agent_types=agent_types,
            stopping_config=cfg.stopping,
        )
        sim._config = cfg  # retained verbatim, see to_config() below
        return sim

    def to_config(self) -> dict:
        return self._config.model_dump(mode="json")

