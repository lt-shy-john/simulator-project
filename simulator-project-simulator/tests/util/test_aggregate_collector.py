"""Tests for the Aggregate Stats Collector (S-09)."""
import pytest

from util.collector import (
    AggregateCollectorConfig,
    AggregateConfigError,
    compile_aggregates,
    collect_aggregates,
)
from behaviour.base import BehaviourModule
from behaviour.registry import register_behaviour, _registry
from behaviour.executor import run_step
from behaviour.executor import compile_behaviours
from behaviour.model import SimulationModel
from scheduler.scheduler import compile_scheduling
from topology.topology import build_topologies
from runner.soa import to_soa

def _base_config():
    if "noOpModule" not in _registry:
        @register_behaviour("noOpModule")
        class _NoOpModule(BehaviourModule):
            def apply(self, agent, neighbours, accessor, model):
                pass
    return {
        "topologies": {
            "sample_network": {
                "mode": "all_pairs",
                "agent_types": ["person"],
                "allow_self_interaction": True,
            }
        },
        "scheduling": {"order": "all_at_once", "read_mode": "frozen"},
        "behaviour": {
            "person": [
                {"module": "noOpModule", "write_mode": "deferred", "topology_name": "sample_network"}
            ]
        },
    }

def _run_one_step(sample_agents_dict, person_agent_types, collectors):
    config = _base_config()
    soa = to_soa([agent for agent in sample_agents_dict.values()])
    pairs = build_topologies(config, soa)
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config,
              person_agent_types, 1, aggregate_collectors=collectors)
    return model


# --- Config validation ---

def test_compile_aggregates_valid_config():
    config = {"aggregates": [
        {"name": "infected_count", "type": "count", "filter_expr": "status=='I'"},
        {"name": "mean_wealth", "type": "mean", "filter_expr": "True", "attr": "wealth"},
    ]}
    collectors = compile_aggregates(config)
    assert len(collectors) == 2
    assert collectors[0].name == "infected_count"
    assert collectors[1].attr == "wealth"


def test_compile_aggregates_no_config_section_returns_empty():
    assert compile_aggregates({}) == []


def test_compile_aggregates_count_does_not_require_attr():
    config = {"aggregates": [{"name": "infected_count", "type": "count", "filter_expr": "status=='I'"}]}
    collectors = compile_aggregates(config)
    assert collectors[0].attr is None


def test_compile_aggregates_mean_missing_attr_raises():
    config = {"aggregates": [{"name": "mean_wealth", "type": "mean", "filter_expr": "True"}]}
    with pytest.raises(AggregateConfigError):
        compile_aggregates(config)


def test_compile_aggregates_sum_missing_attr_raises():
    config = {"aggregates": [{"name": "total_wealth", "type": "sum", "filter_expr": "True"}]}
    with pytest.raises(AggregateConfigError):
        compile_aggregates(config)


def test_compile_aggregates_missing_filter_expr_raises():
    config = {"aggregates": [{"name": "infected_count", "type": "count"}]}
    with pytest.raises(AggregateConfigError):
        compile_aggregates(config)


def test_compile_aggregates_duplicate_name_raises():
    config = {"aggregates": [
        {"name": "infected_count", "type": "count", "filter_expr": "status=='I'"},
        {"name": "infected_count", "type": "count", "filter_expr": "status=='R'"},
    ]}
    with pytest.raises(AggregateConfigError):
        compile_aggregates(config)


@pytest.mark.parametrize("reserved_name", ["step", "agent_count"])
def test_compile_aggregates_reserved_name_raises(reserved_name):
    config = {"aggregates": [{"name": reserved_name, "type": "count", "filter_expr": "True"}]}
    with pytest.raises(AggregateConfigError):
        compile_aggregates(config)


# --- Row shape / collection ---

def test_collect_aggregates_zero_collectors_still_has_agent_count(sample_agents_dict):
    model = SimulationModel()
    model._reset_for_step(1, sample_agents_dict)

    row = collect_aggregates(model, [])

    assert set(row.keys()) == {"step", "agent_count"}
    assert row["step"] == 1
    assert isinstance(row["agent_count"], dict)


def test_collect_aggregates_builtin_breakdown_by_type(sample_agents_dict, person_agent_types):
    model = SimulationModel()
    model._reset_for_step(1, sample_agents_dict)

    row = collect_aggregates(model, [])

    assert row["agent_count"] == {"person": len(sample_agents_dict)}


def test_collect_aggregates_user_collector_added_as_column(sample_agents_dict):
    model = SimulationModel()
    model._reset_for_step(1, sample_agents_dict)
    collectors = [AggregateCollectorConfig(name="all_agents", type="count", filter_expr="True")]

    row = collect_aggregates(model, collectors)

    assert row["all_agents"] == len(sample_agents_dict)
    assert set(row.keys()) == {"step", "agent_count", "all_agents"}


# --- End-to-end via run_step ---

def test_run_step_appends_one_aggregate_row_per_step(sample_agents_dict, person_agent_types):
    collectors = [AggregateCollectorConfig(name="all_agents", type="count", filter_expr="True")]

    model = _run_one_step(sample_agents_dict, person_agent_types, collectors)

    aggregates = model.get_aggregates()
    assert len(aggregates) == 1
    assert aggregates[0]["step"] == 1
    assert aggregates[0]["all_agents"] == len(sample_agents_dict)


def test_run_step_zero_collectors_still_produces_agent_count_row(sample_agents_dict, person_agent_types):
    model = _run_one_step(sample_agents_dict, person_agent_types, collectors=[])

    aggregates = model.get_aggregates()
    assert len(aggregates) == 1
    assert set(aggregates[0].keys()) == {"step", "agent_count"}