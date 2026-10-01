"""Application configuration.

All configuration is environment driven (12-factor). Values are validated at start-up so a
misconfigured deployment fails fast instead of misbehaving at runtime.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]

_INSECURE_SIGNING_SECRET = "insecure-dev-signing-secret-change-me"  # noqa: S105 - documented dev default

LLMProviderName = Literal["local", "bedrock", "gemini"]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMTask(StrEnum):
    """Logical AI workloads. Each can be routed to a different provider/model."""

    EXTRACTION = "extraction"
    MATCH = "match"
    RESUME = "resume"
    OUTREACH = "outreach"
    RESEARCH = "research"
    APPLICATION = "application"
    PROFILE_IMPORT = "profile_import"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", API_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------------------
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_name: str = "CareerOS"
    log_level: str = "INFO"
    log_json: bool | None = None  # defaults to JSON everywhere except development

    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Database ----------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://careeros:careeros@localhost:5433/careeros"
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_echo: bool = False

    # --- Authentication ----------------------------------------------------------------
    # dev: static token (local only) · password: self-hosted email + password accounts ·
    # firebase: Firebase ID tokens
    auth_mode: Literal["firebase", "password", "dev"] = "dev"
    firebase_project_id: str | None = None
    firebase_client_email: str | None = None
    firebase_private_key: SecretStr | None = None
    dev_auth_token: SecretStr = SecretStr("dev-token")
    dev_auth_email: str = "dev@careeros.local"
    dev_auth_name: str = "CareerOS Developer"

    # --- Secrets -----------------------------------------------------------------------
    encryption_key: SecretStr | None = None  # Fernet key protecting OAuth tokens at rest
    signing_secret: SecretStr = SecretStr(_INSECURE_SIGNING_SECRET)

    # --- Internal endpoints (Cloud Scheduler / Pub/Sub push) ---------------------------
    internal_auth_mode: Literal["oidc", "token"] = "token"
    internal_api_token: SecretStr = SecretStr("dev-internal-token")
    internal_oidc_audience: str | None = None
    internal_oidc_service_account: str | None = None

    # --- Google Cloud ------------------------------------------------------------------
    google_cloud_project: str | None = None
    google_cloud_region: str = "us-central1"
    pubsub_topic_discovery: str = "careeros-discovery"
    pubsub_topic_analysis: str = "careeros-analysis"
    pubsub_topic_application: str = "careeros-application"
    pubsub_topic_outreach: str = "careeros-outreach"
    task_dispatch_mode: Literal["database", "pubsub"] = "database"

    storage_backend: Literal["local", "gcs"] = "local"
    local_storage_dir: Path = REPO_ROOT / ".storage"
    gcs_bucket: str | None = None

    # --- LLM routing -------------------------------------------------------------------
    llm_extraction_provider: LLMProviderName = "local"
    llm_match_provider: LLMProviderName = "local"
    llm_resume_provider: LLMProviderName = "local"
    llm_outreach_provider: LLMProviderName = "local"
    llm_research_provider: LLMProviderName = "local"
    llm_application_provider: LLMProviderName = "local"
    llm_profile_import_provider: LLMProviderName = "local"
    embedding_provider: LLMProviderName = "local"
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 2

    aws_region: str = "us-east-1"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_session_token: SecretStr | None = None
    bedrock_model_default: str | None = None
    bedrock_model_extraction: str | None = None
    bedrock_model_match: str | None = None
    bedrock_model_resume: str | None = None
    bedrock_model_outreach: str | None = None
    bedrock_model_research: str | None = None
    bedrock_model_application: str | None = None
    bedrock_model_profile_import: str | None = None
    bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"

    gemini_api_key: SecretStr | None = None
    # Vertex AI mode uses Application Default Credentials instead of an API key.
    gemini_use_vertexai: bool = False
    gemini_vertex_location: str = "global"
    gemini_model_default: str | None = None
    gemini_model_extraction: str | None = None
    gemini_model_match: str | None = None
    gemini_model_resume: str | None = None
    gemini_model_outreach: str | None = None
    gemini_model_research: str | None = None
    gemini_model_application: str | None = None
    gemini_model_profile_import: str | None = None
    gemini_embedding_model: str = "gemini-embedding-2"

    # --- Email -------------------------------------------------------------------------
    email_provider: Literal["mock", "gmail"] = "mock"
    gmail_client_id: str | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gmail/callback"
    # Outreach emails the user sends from their own Gmail in any 24 hours (protects the sender's
    # reputation; every email still needs an explicit send).
    outreach_daily_limit: int = Field(20, ge=1, le=100)

    # --- Push notifications (Firebase Cloud Messaging) ---------------------------------
    # Set to the Firebase project id to push alerts to phones. On GCE the VM's service account
    # authenticates (metadata server); it needs the FCM sender role and the cloud-platform scope.
    fcm_project_id: str | None = None

    # --- Web search (company research / contact discovery) ----------------------------
    search_provider: Literal["none", "brave", "google_cse"] = "none"
    brave_search_api_key: SecretStr | None = None
    google_cse_api_key: SecretStr | None = None
    google_cse_engine_id: str | None = None

    # --- Browser automation ------------------------------------------------------------
    playwright_headless: bool = True
    browser_navigation_timeout_ms: int = 30_000

    # --- Human-in-the-loop safety switches ---------------------------------------------
    auto_submit_applications: bool = False
    auto_send_emails: bool = False

    # --- Resume rendering --------------------------------------------------------------
    latex_engine: Literal["auto", "tectonic", "xelatex", "lualatex", "pdflatex"] = "auto"
    latex_timeout_seconds: int = 240

    # --- Outbound HTTP politeness ------------------------------------------------------
    http_user_agent: str = (
        "CareerOS/0.1 (personal career agent; +https://github.com/itzsam-lol/careeros)"
    )
    http_timeout_seconds: float = 20.0
    http_max_response_bytes: int = 5_000_000
    http_min_host_interval_seconds: float = 1.5
    http_respect_robots_txt: bool = True

    # --- Workers -----------------------------------------------------------------------
    worker_poll_interval_seconds: float = 2.0
    worker_concurrency: int = 4
    task_max_attempts: int = 5
    task_lease_seconds: int = 900

    # --- API protection ----------------------------------------------------------------
    api_rate_limit_per_minute: int = 240

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        # Accept plain postgres URLs (Cloud SQL, CI services) and pin the async driver.
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def _validate_safety(self) -> Settings:
        if self.auto_submit_applications:
            raise ValueError(
                "AUTO_SUBMIT_APPLICATIONS=true is not supported: every application submission "
                "requires explicit user approval."
            )
        if self.auto_send_emails:
            raise ValueError(
                "AUTO_SEND_EMAILS=true is not supported: every outreach email requires explicit "
                "user approval."
            )
        if self.is_deployed:
            problems: list[str] = []
            if self.auth_mode == "dev":
                problems.append("AUTH_MODE must be 'password' or 'firebase'")
            if self.auth_mode == "firebase" and not self.firebase_project_id:
                problems.append("FIREBASE_PROJECT_ID is required")
            if self.encryption_key is None:
                problems.append("ENCRYPTION_KEY is required")
            secret = self.signing_secret.get_secret_value()
            if secret == _INSECURE_SIGNING_SECRET or len(secret) < 32:
                problems.append("SIGNING_SECRET must be a random value of at least 32 characters")
            if self.internal_auth_mode == "oidc":
                if not self.internal_oidc_audience or not self.internal_oidc_service_account:
                    problems.append(
                        "INTERNAL_OIDC_AUDIENCE and INTERNAL_OIDC_SERVICE_ACCOUNT are required"
                    )
            elif len(self.internal_api_token.get_secret_value()) < 32:
                problems.append(
                    "INTERNAL_API_TOKEN must be a random value of at least 32 characters"
                )
            if "*" in self.cors_origins:
                problems.append("CORS_ORIGINS must not contain '*'")
            if self.storage_backend == "gcs" and not self.gcs_bucket:
                problems.append("GCS_BUCKET is required when STORAGE_BACKEND=gcs")
            if problems:
                raise ValueError("Unsafe deployed configuration: " + "; ".join(problems))
        return self

    @property
    def is_deployed(self) -> bool:
        return self.app_env in (AppEnv.STAGING, AppEnv.PRODUCTION)

    @property
    def use_json_logs(self) -> bool:
        if self.log_json is not None:
            return self.log_json
        return self.app_env != AppEnv.DEVELOPMENT

    def provider_for(self, task: LLMTask) -> LLMProviderName:
        provider: LLMProviderName = getattr(self, f"llm_{task.value}_provider")
        return provider

    def model_for(self, provider: LLMProviderName, task: LLMTask) -> str | None:
        """Model id for a provider/task pair, falling back to the provider default."""
        if provider == "local":
            return "local-heuristic"
        specific: str | None = getattr(self, f"{provider}_model_{task.value}", None)
        default: str | None = getattr(self, f"{provider}_model_default", None)
        return specific or default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
