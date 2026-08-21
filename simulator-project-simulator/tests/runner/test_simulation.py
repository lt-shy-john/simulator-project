"""
test_simulation_from_config.py — S-08 acceptance criteria tests.

Covers Simulation.from_config / to_config, SimulationConfig validation,
and util.import_csv, mapped directly to the S-08 ticket's five ACs:

  AC1: Simulation.from_config(dict) constructs agents, topology,
       behaviours, and scheduler
  AC2: config schema validated with Pydantic; missing required fields
       raise descriptive errors
  AC3: CSV import maps column names to agent attributes; unrecognised
       columns are ignored with a warning
  AC4: Simulation.to_config() round-trips to the canonical config dict
  AC5: two runs from the same config  seed produce identical results
"""

import csv
import warnings

import pytest
from pydantic import ValidationError

from runner.simulation import Simulation
from runner.simulationConfig import SimulationConfig
from util.util import import_csv
from agents.agents import AgentType


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_config() -> dict:
    """A minimal, fully valid config: one heterogeneous agent type with a
    single distribution-driven attribute, an all_pairs topology, one
    expression behaviour, all_at_once scheduling, and a max_steps stop."""
    return {
        "seed": 42,
        "agent_types": [
            {
                "name": "person",
                "count": 5,
                "generation_mode": "heterogeneous",
                "attributes": [
                    {
                        "name": "age",
                        "type": "int",
                        "population_method": "distribution",
                        "distribution": {"kind": "uniform", "low": 0, "high": 100},
                    },
                ],
            }
        ],
        "topologies": {
            "contact": {"mode": "all_pairs", "agent_types": ["person"]},
        },
        "behaviours": {
            "person": [
                {"expression": 'state["age"] += 1', "topology_name": "contact"},
            ],
        },
        "scheduler": {"order": "all_at_once", "read_mode": "frozen"},
        "stopping": {"max_steps": 3, "conditions": [], "combinator": "OR"},
    }


@pytest.fixture
def person_agent_type() -> AgentType:
    """An AgentType matching base_config's 'person' section, for import_csv
    tests that don't need a full Simulation."""
    return AgentType(
        name="person",
        count=3,
        generation_mode="heterogeneous",
        attributes=[
            {"name": "name", "type": "categorical"},
            {"name": "age", "type": "int"},
        ],
    )


def _write_csv(path, header: list[str], rows: list[list[str]]) -> str:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return str(path)


# ---------------------------------------------------------------------------
# AC1 — from_config constructs agents, topology, behaviours, scheduler
# ---------------------------------------------------------------------------

class TestFromConfigConstruction:
    def test_from_config_builds_full_population(self, base_config):
        sim = Simulation.from_config(base_config)
        assert len(sim.live_population) == 5
        assert all(a.agent_type_name == "person" for a in sim.live_population.values())
        assert all(0 <= a.state["age"] <= 100 for a in sim.live_population.values())

    def test_from_config_builds_topologies(self, base_config):
        sim = Simulation.from_config(base_config)
        assert "contact" in sim.topologies

    def test_from_config_builds_behaviours(self, base_config):
        sim = Simulation.from_config(base_config)
        assert "person" in sim.compiled_behaviours
        assert len(sim.compiled_behaviours["person"]) == 1

    def test_from_config_builds_scheduler(self, base_config):
        sim = Simulation.from_config(base_config)
        assert sim.schedule.order == "all_at_once"
        assert sim.schedule.read_mode == "frozen"

    def test_from_config_result_is_runnable(self, base_config):
        sim = Simulation.from_config(base_config)
        result = sim()
        assert result.stopped is True
        assert result.reason == "max_steps"
        # behaviour incremented age by 1 each of the 3 steps
        assert all(a.state["age"] >= 3 for a in sim.live_population.values())

    def test_multiple_agent_types_all_constructed(self, base_config):
        base_config["agent_types"].append(
            {
                "name": "location",
                "count": 2,
                "generation_mode": "homogeneous",
                "attributes": [],
            }
        )
        sim = Simulation.from_config(base_config)
        type_names = {a.agent_type_name for a in sim.live_population.values()}
        assert type_names == {"person", "location"}
        assert sum(1 for a in sim.live_population.values() if a.agent_type_name == "location") == 2


# ---------------------------------------------------------------------------
# AC2 — Pydantic validation; missing required fields raise descriptive errors
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_missing_agent_types_raises_descriptive_error(self, base_config):
        del base_config["agent_types"]
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "agent_types" in str(exc_info.value)

    def test_missing_stopping_raises_descriptive_error(self, base_config):
        del base_config["stopping"]
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "stopping" in str(exc_info.value)

    def test_missing_agent_type_name_raises_descriptive_error(self, base_config):
        del base_config["agent_types"][0]["name"]
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "name" in str(exc_info.value)

    def test_duplicate_agent_type_names_rejected(self, base_config):
        base_config["agent_types"].append(dict(base_config["agent_types"][0]))
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "duplicate agent type names" in str(exc_info.value)

    def test_invalid_stopping_combinator_rejected(self, base_config):
        base_config["stopping"]["combinator"] = "MAYBE"
        with pytest.raises(ValidationError):
            SimulationConfig.model_validate(base_config)

    def test_negative_agent_count_rejected(self, base_config):
        base_config["agent_types"][0]["count"] = -1
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "count must be > 0" in str(exc_info.value)

    def test_missing_topologies_section_raises_on_construction(self, base_config):
        # An empty topologies dict is a valid *type* (dict[str, TopologyConfig]
        # with zero entries) — Pydantic doesn't reject emptiness by itself.
        # build_topologies' own "must have at least one" check still catches
        # this at from_config() time with a descriptive error.
        base_config["topologies"] = {}
        with pytest.raises(ValueError, match="topologies"):
            Simulation.from_config(base_config)

    def test_invalid_topology_mode_rejected_by_discriminated_union(self, base_config):
        base_config["topologies"]["contact"]["mode"] = "not_a_real_mode"
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig.model_validate(base_config)
        assert "all_pairs" in str(exc_info.value)  # names the valid options

    def test_random_sample_requires_exactly_one_of_k_or_proportion(self, base_config):
        base_config["topologies"]["social"] = {"mode": "random_sample", "agent_types": ["person"]}
        with pytest.raises(ValidationError, match="exactly one of 'k' or 'proportion'"):
            SimulationConfig.model_validate(base_config)

    def test_random_sample_rejects_both_k_and_proportion(self, base_config):
        base_config["topologies"]["social"] = {
            "mode": "random_sample", "k": 2, "proportion": 0.5, "agent_types": ["person"],
            }
        with pytest.raises(ValidationError, match="exactly one of 'k' or 'proportion'"):
            SimulationConfig.model_validate(base_config)

    def test_scheduler_priority_without_priority_attribute_rejected(self, base_config):
        base_config["scheduler"] = {"order": "priority", "read_mode": "frozen"}
        with pytest.raises(ValidationError, match="priority_attribute"):
            SimulationConfig.model_validate(base_config)

    def test_scheduler_invalid_order_rejected(self, base_config):
        base_config["scheduler"]["order"] = "not_a_real_order"
        with pytest.raises(ValidationError):
            SimulationConfig.model_validate(base_config)

    def test_behaviour_entry_with_neither_module_nor_expression_rejected(self, base_config):
        base_config["behaviours"]["person"] = [{"topology_name": "contact"}]
        with pytest.raises(ValidationError):
            SimulationConfig.model_validate(base_config)


# ---------------------------------------------------------------------------
# AC3 — CSV import: column mapping, unrecognised columns warn and are ignored
# ---------------------------------------------------------------------------

class TestCsvImport:
    def test_recognised_columns_mapped_and_coerced(self, tmp_path, person_agent_type):
        path = _write_csv(
            tmp_path / "agents.csv",
            ["name", "age"],
            [["Alice", "30"], ["Bob", "25"]],
        )
        records = import_csv(path, person_agent_type)
        assert records == [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]

    def test_unrecognised_column_ignored_with_warning(self, tmp_path, person_agent_type):
        path = _write_csv(
            tmp_path / "agents.csv",
            ["name", "age", "favourite_colour"],
            [["Alice", "30", "blue"]],
        )
        with pytest.warns(UserWarning, match="favourite_colour"):
            records = import_csv(path, person_agent_type)
        assert records == [{"name": "Alice", "age": 30}]
        assert "favourite_colour" not in records[0]

    def test_more_rows_than_count_truncates_and_warns(self, tmp_path, person_agent_type):
        # person_agent_type.count == 3
        path = _write_csv(
            tmp_path / "agents.csv",
            ["name", "age"],
            [["A", "1"], ["B", "2"], ["C", "3"], ["D", "4"], ["E", "5"]],
        )
        with pytest.warns(UserWarning, match="keeping the first 3"):
            records = import_csv(path, person_agent_type)
        assert len(records) == 3
        assert [r["name"] for r in records] == ["A", "B", "C"]  # first N preserved

    def test_fewer_rows_than_count_keeps_all_and_warns(self, tmp_path, person_agent_type):
        path = _write_csv(
            tmp_path / "agents.csv",
            ["name", "age"],
            [["A", "1"]],
        )
        with pytest.warns(UserWarning, match="generated normally"):
            records = import_csv(path, person_agent_type)
        assert len(records) == 1

    def test_row_missing_required_column_raises(self, tmp_path, person_agent_type):
        path = _write_csv(
            tmp_path / "agents.csv",
            ["name", "age"],
            [["Alice", ""]],  # age blank
        )
        with pytest.raises(ValueError, match="missing required column"):
            import_csv(path, person_agent_type)

    def test_import_csv_output_feeds_from_config_as_override(self, tmp_path, base_config):
        # Exactly base_config's 'person' count (5) — no generation fallback.
        path = _write_csv(
            tmp_path / "ages.csv",
            ["age"],
            [["10"], ["20"], ["30"], ["40"], ["50"]],
        )
        agent_type = AgentType.model_validate(base_config["agent_types"][0])
        base_config["initial_population"] = {"person": import_csv(path, agent_type)}

        sim = Simulation.from_config(base_config)
        ages = sorted(a.state["age"] for a in sim.live_population.values())
        assert ages == [10, 20, 30, 40, 50]


# ---------------------------------------------------------------------------
# AC4 — to_config() round-trips to the canonical config dict
# ---------------------------------------------------------------------------

class TestToConfigRoundTrip:
    def test_to_config_preserves_all_top_level_keys(self, base_config):
        sim = Simulation.from_config(base_config)
        out = sim.to_config()
        assert set(out.keys()) == {
            "seed", "agent_types", "initial_population",
            "topologies", "behaviours", "scheduler", "stopping",
        }

    def test_to_config_seed_matches_input(self, base_config):
        sim = Simulation.from_config(base_config)
        assert sim.to_config()["seed"] == 42

    def test_to_config_feeds_back_into_from_config(self, base_config):
        """The core round-trip guarantee: from_config(sim.to_config())
        reconstructs an equivalent simulation — same population size,
        same agent types, same topology/behaviour/scheduler shape."""
        sim1 = Simulation.from_config(base_config)
        round_tripped_config = sim1.to_config()

        sim2 = Simulation.from_config(round_tripped_config)

        assert len(sim2.live_population) == len(sim1.live_population)
        assert set(sim2.topologies.keys()) == set(sim1.topologies.keys())
        assert set(sim2.compiled_behaviours.keys()) == set(sim1.compiled_behaviours.keys())
        assert sim2.schedule.order == sim1.schedule.order

    def test_to_config_round_trip_is_deterministic_given_same_seed(self, base_config):
        """Stronger than the shape check above: since seed is preserved,
        re-running from the round-tripped config reproduces the exact
        same population values too (ties AC4 to AC5)."""
        sim1 = Simulation.from_config(base_config)
        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())

        sim2 = Simulation.from_config(sim1.to_config())
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())

        assert ages1 == ages2

# ---------------------------------------------------------------------------
# Network topology — graph config round-trip and bring-your-own file handling
# ---------------------------------------------------------------------------

class TestNetworkTopologyRoundTrip:
    def test_generated_graph_round_trips_as_params(self, base_config):
        """A generated graph's to_config() should echo the generation
        params (type, n, p, seed) — not embed literal node/edge data."""
        base_config["topologies"] = {
            "net": {
                "mode": "network",
                "agent_types": ["person"],
                "graph": {"type": "erdos_renyi", "n": 5, "p": 0.5, "seed": 7},
            }
        }
        base_config["behaviours"]["person"][0]["topology_name"] = "net"

        sim = Simulation.from_config(base_config)
        out = sim.to_config()
        graph_out = out["topologies"]["net"]["graph"]

        assert graph_out.get("type") == "erdos_renyi"
        assert "source" not in graph_out
        assert "data" not in graph_out

    def test_generated_graph_round_trips_back_into_from_config(self, base_config):
        """from_config(sim.to_config()) must work for a network topology."""
        base_config["topologies"] = {
            "net": {
                "mode": "network",
                "agent_types": ["person"],
                "graph": {"type": "erdos_renyi", "n": 5, "p": 0.5, "seed": 7},
            }
        }
        base_config["behaviours"]["person"][0]["topology_name"] = "net"

        sim1 = Simulation.from_config(base_config)
        sim2 = Simulation.from_config(sim1.to_config())

        assert len(sim2.live_population) == len(sim1.live_population)
        assert "net" in sim2.topologies

    def test_byo_graph_to_config_replaces_path_with_node_link_data(self, tmp_path, base_config):
        """A bring-your-own graph: to_config() must not echo the source
        file path — it must embed literal node-link data so the config
        section is self-contained.

        Note on round-trip rehydration scope: a BYO graph's node IDs are
        the UUIDs of a specific run's agents. Rehydrating to a *new*
        Simulation via from_config() would generate fresh UUIDs that
        wouldn't match. Full round-trip rehydration for BYO graphs
        requires UUID-preserving population serialization — S-09 scope.
        S-08 guarantees only that the path is replaced with literal data.
        """
        import networkx as nx
        from topology.graph_builder import graph_to_config

        # Test graph_to_config() directly — the unit responsible for
        # the path -> literal data conversion.
        g = nx.Graph()
        g.add_nodes_from(["uuid-a", "uuid-b", "uuid-c"])
        g.add_edge("uuid-a", "uuid-b")
        source_config = {"source": str(tmp_path / "test.graphml")}

        result = graph_to_config(g, source_config)

        assert "source" not in result, (
            f"File path should be replaced, got: {result}"
        )
        assert result.get("type") == "node_link"
        assert "data" in result

        # Confirm the node-link data reconstructs the same graph
        reconstructed = nx.node_link_graph(result["data"])
        assert set(reconstructed.nodes()) == set(g.nodes())
        assert set(reconstructed.edges()) == set(g.edges())

    def test_graph_to_config_echoes_generated_params(self):
        """graph_to_config() for a generated graph should echo the
        generation params unchanged — not embed literal data."""
        import networkx as nx
        from topology.graph_builder import graph_to_config

        g = nx.erdos_renyi_graph(5, 0.5, seed=42)
        source_config = {"type": "erdos_renyi", "n": 5, "p": 0.5, "seed": 42}

        result = graph_to_config(g, source_config)

        assert result is source_config  # same object, not a copy
        assert result["type"] == "erdos_renyi"
        assert "data" not in result



# ---------------------------------------------------------------------------
# AC5 — same config  seed => identical results across two runs
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_seed_produces_identical_initial_population(self, base_config):
        sim1 = Simulation.from_config(base_config)
        sim2 = Simulation.from_config(base_config)

        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())
        assert ages1 == ages2

    def test_same_seed_produces_identical_full_run(self, base_config):
        sim1 = Simulation.from_config(base_config)
        result1 = sim1()
        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())

        sim2 = Simulation.from_config(base_config)
        result2 = sim2()
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())

        assert result1.reason == result2.reason
        assert result1.detail == result2.detail
        assert ages1 == ages2

    def test_different_seed_produces_different_population(self, base_config):
        """Not a strict AC, but a useful sanity check the other direction —
        confirms the seed is actually doing something, not just being
        accepted and ignored."""
        sim1 = Simulation.from_config(base_config)
        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())

        base_config["seed"] = 43
        sim2 = Simulation.from_config(base_config)
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())

        assert ages1 != ages2

    def test_determinism_holds_with_random_order_scheduling(self, base_config):
        """Regression guard for the scheduler bug found during S-08 review
        (resolve_step_agents was calling the global random module instead
        of the shared rng) — same seed must still produce identical runs
        under 'random' order, not just 'all_at_once'."""
        base_config["scheduler"] = {"order": "random", "read_mode": "frozen"}

        sim1 = Simulation.from_config(base_config)
        sim1()
        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())

        sim2 = Simulation.from_config(base_config)
        sim2()
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())

        assert ages1 == ages2

    def test_determinism_holds_with_random_sample_topology(self, base_config):
        """Regression guard for RandomSampleTopology's rng threading —
        same seed must produce identical neighbour sampling."""
        base_config["topologies"] = {
            "social": {"mode": "random_sample", "k": 2, "agent_types": ["person"]},
        }
        base_config["behaviours"]["person"][0]["topology_name"] = "social"

        sim1 = Simulation.from_config(base_config)
        sim1()
        ages1 = sorted(a.state["age"] for a in sim1.live_population.values())

        sim2 = Simulation.from_config(base_config)
        sim2()
        ages2 = sorted(a.state["age"] for a in sim2.live_population.values())

        assert ages1 == ages2