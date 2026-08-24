from pathlib import Path
import yaml
from langchain.chat_models import init_chat_model

# Points directly to root/config/agents.yaml
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "agents.yaml"


def load_agent_config(agent_name: str) -> dict:
    """Reads configuration parameters for a given agent from agents.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found at: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    if agent_name not in config:
        raise KeyError(
            f"Agent '{agent_name}' not defined in {CONFIG_PATH.name}"
        )

    return config[agent_name]


def get_agent_model(agent_name: str):
    """Instantiates and returns the configured LLM for the given agent."""
    cfg = load_agent_config(agent_name)

    return init_chat_model(
        model=cfg["model"],
        model_provider=cfg.get("provider"),
        temperature=cfg.get("temperature", 0.0),
    )