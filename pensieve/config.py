"""Runtime configuration loaded from .env / environment."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent

# Installed build (PyInstaller, see desktop/installer/): program files are
# read-only, so per-user data and settings live under %LOCALAPPDATA%\Pensieve.
# Settings come from the install folder's pensieve.env (defaults baked in by the
# installer), then the user's own pensieve.env, then environment variables.
FROZEN = bool(getattr(sys, "frozen", False))
USER_HOME = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Pensieve"
INSTALL_ROOT = Path(sys.executable).resolve().parent.parent if FROZEN else REPO_ROOT
ENV_FILES = (
    (str(INSTALL_ROOT / "pensieve.env"), str(USER_HOME / "pensieve.env")) if FROZEN else (str(REPO_ROOT / ".env"),)
)
DEFAULT_DATA_DIR = USER_HOME / "data" if FROZEN else REPO_ROOT / "data"


class Settings(BaseSettings):
    """All Pensieve runtime settings.

    Loaded from .env in the repo root, with environment variables overriding.
    Most values mirror the existing PowerShell Phase 0 conventions so a single
    .env serves both stacks during the transition.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # --- LLM provider selection ---
    # "github_copilot" (default) routes every LLM call through the GitHub
    #   Copilot SDK under the GitHub account in COPILOT_GITHUB_USER.
    # "azure_openai" routes through an Azure OpenAI deployment (keyless).
    # "github_models" routes through GitHub Models with a PAT.
    llm_provider: Literal["github_copilot", "azure_openai", "github_models"] = Field(
        default="github_copilot", alias="LLM_PROVIDER"
    )

    # --- GitHub Copilot (default LLM provider) ---
    # GitHub login whose Copilot license pays for and governs the calls. The
    # token is read from `gh auth token --user <login>` at runtime.
    copilot_github_user: str = Field(default="", alias="COPILOT_GITHUB_USER")
    # Explicit token fallback when gh is not available. Prefer the user above.
    copilot_github_token: str = Field(default="", alias="COPILOT_GITHUB_TOKEN")
    # Copilot model id (see `client.list_models()`), e.g. gpt-5.4, claude-sonnet-5.5.
    copilot_model: str = Field(default="gpt-5.4", alias="COPILOT_MODEL")
    # Copilot CLI binary. Blank = COPILOT_CLI_PATH env, then the global npm
    # install, then the SDK's own download.
    copilot_cli_path: str = Field(default="", alias="COPILOT_CLI_PATH")
    # Voice capture may create NEW tasks in the user's own list after they
    # confirm (never edits or deletes). The one additive writeback.
    allow_task_create: bool = Field(default=True, alias="PENSIEVE_ALLOW_TASK_CREATE")
    # Vault bridge (pensieve/bridge.py): Obsidian vault root where Pensieve keeps
    # Agents/Pensieve/Now.md and picks up `to: pensieve` task requests. Blank = off.
    vault_dir: str = Field(default="", alias="PENSIEVE_VAULT_DIR")
    # Comma-separated list names agents may see in Now.md. Blank = every list.
    vault_bridge_lists: str = Field(default="", alias="PENSIEVE_VAULT_LISTS")
    # Start the Copilot CLI in the background when the API starts (tests turn this off).
    copilot_prewarm: bool = Field(default=True, alias="COPILOT_PREWARM")

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
    # ReadWrite so voice capture can ADD new tasks; Pensieve never edits or
    # deletes existing ones (see pensieve/capture/creators.py).
    personal_graph_scopes: str = Field(
        default="Tasks.ReadWrite", alias="PERSONAL_GRAPH_SCOPES"
    )
    personal_graph_token_cache_name: str = Field(
        default="personal-graph-token-cache.bin",
        alias="PERSONAL_GRAPH_TOKEN_CACHE_NAME",
    )
    personal_graph_skip_completed_older_days: int = Field(
        default=30, alias="PERSONAL_GRAPH_SKIP_COMPLETED_OLDER_DAYS"
    )

    # --- Pensieve runtime ---
    data_dir: Path = Field(default=DEFAULT_DATA_DIR, alias="PENSIEVE_DATA_DIR")
    backend_port: int = Field(default=8765, alias="PENSIEVE_BACKEND_PORT")
    enrichment_confidence_threshold: float = Field(
        default=0.6, alias="PENSIEVE_ENRICHMENT_CONFIDENCE_THRESHOLD"
    )
    default_list_name: str = Field(default="Tasks", alias="PENSIEVE_DEFAULT_LIST_NAME")

    # Comma-separated list of source list_name values to INCLUDE when
    # generating Connect recaps. Tasks in other lists (e.g. "home", "UW
    # Lectures") are excluded from recap input. Empty string = no filter
    # (include every memory). Default = "CISO GRC" (Andy's work list).
    recap_list_names: str = Field(default="CISO GRC", alias="PENSIEVE_RECAP_LIST_NAMES")

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

    # --- Mirror tag (Phase 2 TaskSink writeback) ---
    # When True, every column drag in Pensieve writes a `pensieve/col:<col>`
    # tag back to the source task's Categories field so a second PC syncing
    # from the same Microsoft To-Do account sees the same kanban view.
    # Default OFF until the user has verified on at least one machine.
    mirror_to_source: bool = Field(default=False, alias="PENSIEVE_MIRROR_TO_SOURCE")
    mirror_tag_prefix: str = Field(default="pensieve/col:", alias="PENSIEVE_MIRROR_TAG_PREFIX")

    # When True, dragging a card to the `closed` column marks the source task
    # complete in its upstream system (Outlook COM → MarkComplete()). This is
    # a SEPARATE opt-in from the column-tag mirror above because completion
    # is a higher-impact write than a category tag: a colleague sharing the
    # task would see it as "done" in Microsoft To-Do, not just see a Pensieve
    # category. v1 is one-way (close only) — dragging OUT of `closed` does
    # NOT reopen the source task; users who want to reopen do it in Outlook
    # and the next sync moves the card out of closed automatically.
    mirror_completion: bool = Field(default=False, alias="PENSIEVE_MIRROR_COMPLETION")

    # --- Auto-sync scheduler ---
    # Backend periodically calls the same code path as `POST /api/sync` so
    # the kanban stays current without manual "Pull from To-Do" clicks. Set
    # to 0 to disable. The scheduler uses the same single-job tracker the
    # manual route uses, so manual and scheduled syncs never collide.
    auto_sync_interval_seconds: int = Field(
        default=120, alias="PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS"
    )
    # Source the scheduler should sync from. Empty string = use
    # `default_source`. Set to `outlook_com` here if your `default_source` is
    # `sample_file` (running auto-sync against a static fixture is pointless,
    # so the scheduler silently skips sample_file ticks).
    auto_sync_source: str = Field(default="", alias="PENSIEVE_AUTO_SYNC_SOURCE")

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

    @property
    def garden_quests_path(self) -> Path:
        """Garden v2 daily quests + clean-day history."""
        return self.data_dir / "garden-quests.json"

    @property
    def achievements_path(self) -> Path:
        """Garden v3 unlocked achievement badges."""
        return self.data_dir / "achievements.json"

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    def personal_graph_scope_list(self) -> list[str]:
        return [s.strip() for s in self.personal_graph_scopes.split(",") if s.strip()]

    @property
    def personal_graph_token_cache_path(self) -> Path:
        return self.data_dir / self.personal_graph_token_cache_name

    def recap_list_names_list(self) -> list[str]:
        return [n.strip() for n in self.recap_list_names.split(",") if n.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
