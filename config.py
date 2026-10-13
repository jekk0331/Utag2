import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    delay_seconds: float
    batch_size: int
    log_level: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan")
    return Config(
        bot_token=token,
        db_path=os.getenv("DB_PATH", "data/tagbot.db"),
        delay_seconds=max(float(os.getenv("DELAY_SECONDS", "2")), 0.5),
        batch_size=min(max(int(os.getenv("BATCH_SIZE", "5")), 1), 30),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
