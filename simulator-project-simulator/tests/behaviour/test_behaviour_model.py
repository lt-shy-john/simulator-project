import pytest

from behaviour.model import Model

class ValidModule:
    """Correctly implements the full Model Protocol shape."""
    step = 0
    agents = []
    params = {}
    rng = None

    def count(self, filter_expr=None):
        pass

    def mean(self, attr, filter_expr=None):
        pass

    def log_event(self, name, agent_id, data):
        pass

class PartialModule:
    """Only implements one of the methods from the Protocol shape."""
    def log_event(self, name, agent_id, data):
        pass

class InvalidModule:
    """Does NOT implement log_event() at all."""
    def some_other_method(self):
        pass

def test_valid_module_satisfies_protocol():
    instance = ValidModule()
    assert isinstance(instance, Model)

def test_partial_implementation_does_not_satisfy_protocol():
    instance = PartialModule()
    assert not isinstance(instance, Model)

def test_invalid_module_does_not_satisfy_protocol():
    instance = InvalidModule()
    assert not isinstance(instance, Model)

def test_valid_module_log_event_call_succeeds_with_stub_args():
    instance = ValidModule()
    # None of these need to be real — apply()'s body does nothing with them here
    result = instance.log_event(name=None, agent_id=None, data=None)
    assert result is None

def test_model_protocol_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Model()