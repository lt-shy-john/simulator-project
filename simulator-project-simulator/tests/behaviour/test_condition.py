import pytest
import random

from behaviour.condition import _evaluate_condition

def test_evaluate_condition_true_success(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    assert _evaluate_condition("state['energy'] < 11", target_agent) == True

def test_evaluate_condition_false_success(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    assert _evaluate_condition("state['energy'] > 10", target_agent) == False

def test_evaluate_condition_non_bool_result_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e :
        _evaluate_condition("state['energy'] + 1", target_agent)
    assert e.match('did not evaluate to a boolean')

def test_evaluate_condition_malicious_expression_rejected(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e :
        _evaluate_condition("__import__('os')", target_agent)
    assert e.match('failed to evaluate safely: ')

def test_evaluate_condition_undefined_name_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e :
        _evaluate_condition("stat['energy'] > 0", target_agent)
    assert e.match('failed to evaluate safely: ')

def test_evaluate_condition_wrong_syntax_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e :
        _evaluate_condition("state['energy'] >", target_agent)
    assert e.match('failed to evaluate: ')

def test_evaluate_condition_wrong_type_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e :
        _evaluate_condition("state['energy'] > 'high'", target_agent)
    assert e.match('failed to evaluate: ')

def test_evaluate_condition_syntax_error_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e:
        _evaluate_condition("state['energy'] >", target_agent)
    assert e.match('failed to evaluate:')  # note: no "safely" here, different branch

def test_evaluate_condition_type_error_raises_value_error(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    with pytest.raises(ValueError) as e:
        _evaluate_condition("state['energy'] > 'high'", target_agent)
    assert e.match('failed to evaluate:')