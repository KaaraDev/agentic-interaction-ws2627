"""Settings from the environment.

The .env file is read when this module is imported; real environment variables take precedence
(load_dotenv does not override variables that are already set).
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .errors import ConfigError

load_dotenv()

REQUIRED = ('OPENAI_BASE_URL', 'MODEL', 'OPENAI_API_KEY', 'DATA_BASE_URL')


@dataclass(frozen=True)
class Config:
    # required
    base_url: str
    model: str
    api_key: str
    data_base_url: str
    # agent loop
    max_steps: int = 30              # model calls per run; reaching it ends the run as an error
    # model requests: Groq counts the reserved output tokens of every request against the
    # tokens-per-minute limit, so a smaller reservation and less reasoning allow more requests
    max_completion_tokens: int = 1536
    reasoning_effort: str = ''       # only understood by some models (gpt-oss); empty = not sent
    temperature: float = 0.3         # lower than the default: fewer malformed tool calls
    # token limit (HTTP 429)
    max_auto_wait_s: float = 10      # shorter waits are simply sat out
    max_unattended_wait_s: float = 600  # unattended: total waiting per run (all pauses together)
    max_pauses: int = 20             # unattended pauses per run
    ask_on_rate_limit: str = 'auto'  # auto | always | never

    @classmethod
    def from_env(cls) -> 'Config':
        missing = [name for name in REQUIRED if not os.getenv(name)]
        if missing:
            raise ConfigError(f"Missing environment variables: {', '.join(missing)}")
        model = os.getenv('MODEL')
        try:
            return cls(
                base_url=os.getenv('OPENAI_BASE_URL').rstrip('/'),
                model=model,
                api_key=os.getenv('OPENAI_API_KEY'),
                data_base_url=os.getenv('DATA_BASE_URL').rstrip('/'),
                max_steps=int(os.getenv('MAX_STEPS', cls.max_steps)),
                max_completion_tokens=int(os.getenv('MAX_COMPLETION_TOKENS', cls.max_completion_tokens)),
                reasoning_effort=os.getenv('REASONING_EFFORT', 'low' if 'gpt-oss' in model else ''),
                max_auto_wait_s=float(os.getenv('MAX_AUTO_WAIT_S', cls.max_auto_wait_s)),
                max_unattended_wait_s=float(os.getenv('MAX_UNATTENDED_WAIT_S', cls.max_unattended_wait_s)),
                ask_on_rate_limit=os.getenv('ASK_ON_RATE_LIMIT', cls.ask_on_rate_limit).lower(),
            )
        except ValueError as e:
            raise ConfigError(f"Invalid number in the configuration: {e}") from None
