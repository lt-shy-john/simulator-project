import json
import yaml

from agents.agents import AgentType

def prompt_int(prompt="> "):
    while True:
        raw = input(prompt).strip()
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")

# Export and import

def agent_type_to_json(agent_type: AgentType) -> str:
    return agent_type.model_dump_json(indent=2)


def agent_type_from_json(data: str) -> AgentType:
    return AgentType.model_validate_json(data)


def agent_type_to_yaml(agent_type: AgentType) -> str:
    return yaml.safe_dump(agent_type.model_dump(mode="json"), sort_keys=False)


def agent_type_from_yaml(data: str) -> AgentType:
    return AgentType.model_validate(yaml.safe_load(data))