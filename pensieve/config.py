"""Runtime configuration loaded from .env / environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All Pensieve runtime settings.

    Loaded from .env in the repo root, with environment variables overriding.
    Most values mirror the existing PowerShell Phase 0 conventions so a single
    .env serves both stacks during the transition.
    """

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # --- LLM provider selection ---
    # "azure_openai" (default) routes enrichment through the Cortex hub.
    # "github_models" routes through GitHub Models with a PAT (personal-device installs).
    llm_provider: Literal["azure_openai", "github_models"] = Field(
        default="azure_openai", alias="LLM_PROVIDER"
    )

    # --- Azure OpenAI (mirrors PowerShell Invoke-AzureOpenAI conventions) ---
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(default="gpt-5.4-2", alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-12-01-preview", alias="AZURE_OPENAI_API_VERSION")
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_token_scope: str = Field(
        default="https://ai.azure.com/.default",
        alias="AZURE_OPENAI_TOKEN_SCOPE",
    )

    # --- GitHub Models (personal-device LLM provider) ---
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_models_base_url: str = Field(
        default="https://models.github.ai/inference", alias="GITHUB_MODELS_BASE_URL"
    )
    github_models_model: str = Field(default="openai/gpt-4o-mini", alias="GITHUB_MODELS_MODEL")

    # --- Personal Microsoft Graph (personal-device task source) ---
    # Personal MS accounts (outlook.com / hotmail / live) work via Graph
    # without admin consent. App registration is created by the user; see
    # docs/SETUP-personal-device.md.
    personal_graph_client_id: str = Field(default="", alias="PERSONAL_GRAPH_CLIENT_ID")
    personal_graph_authority: str = Field(
        default="https://login.microsoftonline.com/consumers",
        alias="PERSONAL_GRAPH_AUTHORITY",
    )
    personal_graph_scopes: str = Field(
        default="Tasks.Read", alias="PERSONAL_GRAPH_SCOPES"
    )
    personal_graph_token_cache_name: str = Field(
        default="personal-graph-token-cache.bin",
        alias="PERSONAL_GRAPH_TOKEN_CACHE_NAME",
    )
    personal_graph_skip_completed_older_days: int = Field(
        default=30, alias="PERSONAL_GRAPH_SKIP_COMPLETED_OLDER_DAYS"
    )

    # --- Pensieve runtime ---
    data_dir: Path = Field(default=REPO_ROOT / "data", alias="PENSIEVE_DATA_DIR")
    backend_port: int = Field(default=8765, alias="PENSIEVE_BACKEND_PORT")
    enrichment_confidence_threshold: float = Field(
        default=0.6, alias="PENSIEVE_ENRICHMENT_CONFIDENCE_THRESHOLD"
    )
    default_list_name: str = Field(default="Tasks", alias="PENSIEVE_DEFAULT_LIST_NAME")

    # --- Chroma ---
    chroma_dir_name: str = Field(default="chroma", alias="PENSIEVE_CHROMA_DIR_NAME")
    chroma_collection_memories: str = Field(default="memories")
    chroma_collection_vials: str = Field(default="vials")

    # --- Enrichment caps ---
    enrichment_max_tokens: int = Field(default=1500, alias="PENSIEVE_ENRICHMENT_MAX_TOKENS")
    enrichment_concurrency: int = Field(default=3, alias="PENSIEVE_ENRICHMENT_CONCURRENCY")

    # --- Sources ---
    default_source: Literal["sample_file", "outlook_com", "personal_graph"] = Field(
        default="sample_file", alias="PENSIEVE_DEFAULT_SOURCE"
    )
    outlook_skip_completed_older_than_days: int = Field(
        default=30, alias="PENSIEVE_OUTLOOK_SKIP_COMPLETED_OLDER_DAYS"
    )

    # --- API ---
    api_cors_origins: str = Field(
        default="http://localhost:8765,http://127.0.0.1:8765,null",
        alias="PENSIEVE_API_CORS_ORIGINS",
    )

    @property
    def prompts_dir(self) -> Path:
        return REPO_ROOT / "prompts"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / self.chroma_dir_name

    @property
    def connect_goals_path(self) -> Path:
        return self.data_dir / "connect-goals.json"

    @property
    def samples_path(self) -> Path:
        return self.data_dir / "samples.json"

    @property
    def audit_log_path(self) -> Path:
        return self.data_dir / "audit-log.jsonl"

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    def personal_graph_scope_list(self) -> list[str]:
        return [s.strip() for s in self.personal_graph_scopes.split(",") if s.strip()]

    @property
    def personal_graph_token_cache_path(self) -> Path:
        return self.data_dir / self.personal_graph_token_cache_name

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
