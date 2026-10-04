from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .tools.api_tools import API_TOOLS


def build_agent():
    settings = get_settings()
    model = ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
    return create_react_agent(model, API_TOOLS, prompt=SYSTEM_PROMPT)
