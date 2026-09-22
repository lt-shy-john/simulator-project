"""
test_commands.py — tests for the interactive CLI's do_setting/do_run flow.

do_setting() drives entirely off builtins.input(), so these tests feed a
scripted sequence of answers rather than mocking individual prompt calls —
that's the only way to exercise the flow the way a real user would type it.
"""

import builtins

import pytest

import runner.commands as commands


@pytest.fixture(autouse=True)
def reset_settings():
    """commands.settings is module-level global state — reset it before
    and after every test so tests don't leak into each other."""
    commands.settings.clear()
    commands.settings["name"] = ""
    yield
    commands.settings.clear()
    commands.settings["name"] = ""


def _run_with_scripted_input(monkeypatch, answers: list[str]):
    scripted = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(scripted))


class TestDoSetting:
    def test_full_flow_builds_valid_runnable_config(self, monkeypatch):
        commands.settings["N"] = 5
        commands.settings["T"] = 3
        _run_with_scripted_input(monkeypatch, [
            "42",                   # seed
            "person",               # agent type name
            "age",                  # attribute name
            "int",                  # type
            "n",                    # not fixed value -> uniform range
            "0",                    # low
            "100",                  # high
            "n",                    # no more attributes
            "all_pairs",            # topology mode
            "contact",              # topology name
            'state["age"] = 1',    # behaviour expression
            "n",                    # don't customise scheduling
        ])

        commands.do_setting()

        assert "config" in commands.settings
        config = commands.settings["config"]
        assert config["agent_types"][0]["name"] == "person"
        assert config["agent_types"][0]["count"] == 5
        assert config["stopping"]["max_steps"] == 3
        assert config["seed"] == 42

    def test_prompts_for_n_and_t_if_missing(self, monkeypatch):
        # No commands.settings["N"]/["T"] pre-set this time.
        _run_with_scripted_input(monkeypatch, [
            "4",                     # N, via set_N()
            "2",                     # T, via set_T()
            "",                      # seed — blank means unseeded
            "person",
            "active",
            "bool",
            "y",                     # fixed value = true (single prompt for bool)
            "n",                     # no more attributes
            "all_pairs",
            "contact",
            'state["active"] = True',
            "n",
        ])

        commands.do_setting()

        assert commands.settings["N"] == 4
        assert commands.settings["T"] == 2
        assert "config" in commands.settings
        assert commands.settings["config"]["seed"] is None

    def test_invalid_config_is_not_saved(self, monkeypatch):
        """Duplicate attribute names -> AgentType's own validator rejects
        it. Nothing should be saved to settings["config"]."""
        commands.settings["N"] = 5
        commands.settings["T"] = 3
        _run_with_scripted_input(monkeypatch, [
            "",                      # seed — blank means unseeded
            "person",
            "age", "int", "n", "0", "100",
            "y",                     # add another attribute
            "age", "int", "n", "0", "50",  # same name again — duplicate
            "n",
            "all_pairs",
            "contact",
            'state["age"] = 1',
            "n",
        ])

        commands.do_setting()

        assert "config" not in commands.settings

    def test_priority_scheduling_prompts_for_priority_attribute(self, monkeypatch):
        commands.settings["N"] = 3
        commands.settings["T"] = 1
        _run_with_scripted_input(monkeypatch, [
            "7",                     # seed
            "person",
            "wealth", "float", "n", "0", "1000",
            "n",
            "all_pairs",
            "contact",
            'state["wealth"] = 1',
            "y",              # customise scheduling
            "priority",
            "wealth",         # priority_attribute
        ])

        commands.do_setting()

        assert commands.settings["config"]["scheduler"]["order"] == "priority"
        assert commands.settings["config"]["scheduler"]["priority_attribute"] == "wealth"

    def test_seed_reprompts_on_non_integer_before_accepting(self, monkeypatch):
        """S-11: an invalid seed answer re-prompts (same behaviour as
        every other int prompt) rather than crashing or silently
        treating garbage input as 'no seed'."""
        commands.settings["N"] = 2
        commands.settings["T"] = 1
        _run_with_scripted_input(monkeypatch, [
            "not-a-number",          # invalid — must re-prompt
            "13",                    # seed, accepted this time
            "person",
            "age", "int", "n", "0", "10", "n",
            "all_pairs", "contact",
            'state["age"] = 1',
            "n",
        ])

        commands.do_setting()

        assert commands.settings["config"]["seed"] == 13


class TestDoRun:
    def test_run_without_config_warns_and_does_not_crash(self):
        # No 'setting' run yet — do_run should warn, not raise.
        commands.do_run()  # should return quietly, not raise

    def test_run_after_setting_executes_successfully(self, monkeypatch):
        commands.settings["N"] = 3
        commands.settings["T"] = 2
        _run_with_scripted_input(monkeypatch, [
            "",                      # seed — blank means unseeded
            "person", "age", "int", "n", "0", "10", "n",
            "all_pairs", "contact",
            'state["age"] = 1',
            "n",
        ])
        commands.do_setting()

        commands.do_run()  # should complete without raising


class TestDefaultConfig:
    def test_default_config_is_valid_and_usable(self):
        from runner.simulationConfig import SimulationConfig
        config = commands.default_config(n=5, t=3)
        SimulationConfig.model_validate(config)  # should not raise
        assert config["agent_types"][0]["count"] == 5
        assert config["stopping"]["max_steps"] == 3

    def test_do_run_default_executes_without_setting(self):
        # No do_setting() call at all — this is the whole point of the
        # express-mode fallback: N/T alone are enough.
        commands.settings["N"] = 4
        commands.settings["T"] = 2
        commands.do_run_default()  # should complete without raising

    def test_do_run_default_warns_without_n_and_t(self):
        commands.do_run_default()  # neither N nor T set — should warn, not raise