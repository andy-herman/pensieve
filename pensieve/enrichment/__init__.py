"""LLM-driven enrichment of RawTask into a Memory."""

from pensieve.enrichment.chat_provider import ChatClient, get_chat_client
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.enrichment.enricher import EnrichmentResult, enrich_task
from pensieve.enrichment.github_models_client import GitHubModelsChatClient
from pensieve.enrichment.llm_client import AzureOpenAIChatClient
from pensieve.enrichment.prompt import load_system_prompt

__all__ = [
    "EnrichmentResult",
    "enrich_task",
    "AzureOpenAIChatClient",
    "GitHubModelsChatClient",
    "ChatClient",
    "get_chat_client",
    "load_connect_goals",
    "load_system_prompt",
]
