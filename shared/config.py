"""Central configuration. FROZEN after kickoff (see schemas.py for the change process).

Everything reads settings through `get_settings()`. Values come from environment variables or
the `.env` file; defaults below are safe for local development.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.schemas import Company, Thresholds

PLACEHOLDER_USER_AGENT = "Your Name your.email@example.com"

# The five demo companies. CIKs are well known but VERIFY them on EDGAR before relying on them
# (https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=AAPL).
COMPANIES: list[Company] = [
    Company(ticker="AAPL", name="Apple Inc.", cik="0000320193"),
    Company(ticker="MSFT", name="Microsoft Corporation", cik="0000789019"),
    Company(ticker="TSLA", name="Tesla, Inc.", cik="0001318605"),
    Company(ticker="NVDA", name="NVIDIA Corporation", cik="0001045810"),
    Company(ticker="AMZN", name="Amazon.com, Inc.", cik="0001018724"),
]


def get_company(ticker: str) -> Company:
    for c in COMPANIES:
        if c.ticker == ticker.upper():
            return c
    raise KeyError(f"Unknown ticker {ticker!r}. Known: {[c.ticker for c in COMPANIES]}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- SEC EDGAR
    sec_user_agent: str = PLACEHOLDER_USER_AGENT
    sec_max_rps: float = 8.0  # SEC allows 10 requests/second; stay under it
    sec_base_url: str = "https://www.sec.gov"
    sec_data_url: str = "https://data.sec.gov"

    # --- Storage
    data_dir: Path = Path("./data")
    audit_db_path: Path = Path("./data/audit.db")
    checkpoint_db_path: Path = Path("./data/checkpoints.db")

    # --- LLM (all providers are used through the OpenAI-compatible API)
    llm_provider: Literal["ollama", "groq", "gemini"] = "ollama"
    llm_model_extract: str = "qwen2.5:7b"
    llm_model_explain: str = "llama3.1:8b"
    llm_timeout_s: float = 60.0
    ollama_base_url: str = "http://localhost:11434/v1"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # --- Default thresholds (the live values are stored by the workflow and editable in the UI)
    confidence_threshold: float = 0.85
    yoy_threshold_pct: float = 40.0
    accounting_tolerance_pct: float = 0.1
    segment_tolerance_pct: float = 0.1
    accuracy_tolerance_pct: float = 0.01  # extraction counts as "correct" within this % of XBRL

    # --- Development switches
    use_fakes: bool = False  # workflow uses workflow/fakes.py instead of real extraction/verification
    use_mock_service: bool = False  # api serves api/mock_service.py instead of the real workflow

    # --- API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    default_reviewer: str = "reviewer"

    # ------------------------------------------------------------------ helpers
    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def filings_dir(self) -> Path:
        return self.data_dir / "filings"

    @property
    def xbrl_dir(self) -> Path:
        return self.data_dir / "xbrl"

    def default_thresholds(self) -> Thresholds:
        return Thresholds(
            confidence=self.confidence_threshold,
            yoy_change_pct=self.yoy_threshold_pct,
            accounting_tolerance_pct=self.accounting_tolerance_pct,
            segment_tolerance_pct=self.segment_tolerance_pct,
        )

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.filings_dir, self.xbrl_dir):
            p.mkdir(parents=True, exist_ok=True)

    def assert_sec_user_agent(self) -> None:
        """Call before the first SEC request. SEC blocks anonymous or placeholder agents."""
        ua = self.sec_user_agent.strip()
        if not ua or ua == PLACEHOLDER_USER_AGENT or "@" not in ua:
            raise RuntimeError(
                "Set SEC_USER_AGENT in .env to 'Your Name your.email@example.com'. "
                "SEC rejects requests without a real contact."
            )

    def llm_base_url_and_key(self) -> tuple[str, str]:
        if self.llm_provider == "ollama":
            return self.ollama_base_url, "ollama"  # key is ignored by Ollama but must be non-empty
        if self.llm_provider == "groq":
            return self.groq_base_url, self.groq_api_key
        return self.gemini_base_url, self.gemini_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
