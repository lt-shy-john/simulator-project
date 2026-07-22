import pytest

from behaviour.base import BehaviourModule
from behaviour.registry import register_behaviour, get_behaviour, list_registered

@pytest.fixture(autouse=True)
def clear_registry():
    from behaviour.registry import _clear_registry_for_testing
    _clear_registry_for_testing()
    yield
    _clear_registry_for_testing()

def test_register_and_get_behaviour_success():
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        pass

    assert get_behaviour("testModule01") == Module01

def test_register_same_class_twice_under_same_name_is_allowed():
    @register_behaviour("testModule01")
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        pass

    assert get_behaviour("testModule01") == Module01

def test_register_different_class_same_name_raises_value_error():
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        pass

    with pytest.raises(ValueError):
        @register_behaviour("testModule01")
        class Module02(BehaviourModule):
            pass

def test_get_unknown_behaviour_raises_key_error():
    with pytest.raises(KeyError):
        get_behaviour('unknown')

def test_list_registered_returns_sorted_names():
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        pass

    @register_behaviour("testModule02")
    class Module02(BehaviourModule):
        pass

    result = list_registered()
    assert result == ['testModule01', 'testModule02']

def test_register_behaviour_decorator_returns_class_unchanged():
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        def __init__(self):
            self.a = 'a'

    module01 = Module01()

    assert type(module01) == Module01
    assert module01.a == 'a'