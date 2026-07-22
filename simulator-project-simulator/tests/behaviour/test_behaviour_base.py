import pytest

from behaviour.base import BehaviourModule

class ValidModule:
    """Correctly implements the Protocol shape."""
    def apply(self, agent, neighbours, accessor, model):
        pass

class InvalidModule:
    """Does NOT implement apply() at all."""
    def some_other_method(self):
        pass

def test_valid_module_satisfies_protocol():
    instance = ValidModule()
    assert isinstance(instance, BehaviourModule)

def test_invalid_module_does_not_satisfy_protocol():
    instance = InvalidModule()
    assert not isinstance(instance, BehaviourModule)

def test_valid_module_apply_call_succeeds_with_stub_args():
    instance = ValidModule()
    # None of these need to be real — apply()'s body does nothing with them here
    result = instance.apply(agent=None, neighbours=[], accessor=None, model=None)
    assert result is None