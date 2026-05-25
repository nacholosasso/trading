"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        print(f"Error: missing required env var {name}. Copy .env.example to .env", file=sys.stderr)
        sys.exit(1)
    return value


def _bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Config:
    binance_api_key: str
    binance_api_secret: str
    binance_base_url: str
    gemini_api_key: str
    gemini_models: tuple[str, ...]
    symbol: str
    interval: str
    klines_limit: int
    loop_interval_sec: int
    quote_order_qty: float
    trade_percent: float
    max_trades_per_day: int
    cooldown_minutes: int
    min_confidence: float
    execute_orders: bool
    logs_dir: str

    @property
    def base_asset(self) -> str:
        if self.symbol.endswith("USDT"):
            return self.symbol[:-4]
        return self.symbol[:3]

    @property
    def quote_asset(self) -> str:
        if self.symbol.endswith("USDT"):
            return "USDT"
        return self.symbol[3:]


DEFAULT_GEMINI_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)


def _parse_gemini_models() -> tuple[str, ...]:
    """Build model try-list: GEMINI_MODEL first, then GEMINI_MODELS or defaults."""
    models: list[str] = []
    primary = os.getenv("GEMINI_MODEL", "").strip()
    if primary:
        models.append(primary)

    extra = os.getenv("GEMINI_MODELS", "").strip()
    if extra:
        for name in extra.split(","):
            name = name.strip()
            if name and name not in models:
                models.append(name)
    else:
        for name in DEFAULT_GEMINI_MODELS:
            if name not in models:
                models.append(name)

    return tuple(models) if models else DEFAULT_GEMINI_MODELS


def load_config() -> Config:
    base_url = _require("BINANCE_BASE_URL").rstrip("/")
    if "testnet" not in base_url.lower():
        print(
            "Error: BINANCE_BASE_URL must point to Binance testnet "
            "(e.g. https://testnet.binance.vision)",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        binance_api_key=_require("BINANCE_API_KEY"),
        binance_api_secret=_require("BINANCE_API_SECRET"),
        binance_base_url=base_url,
        gemini_api_key=_require("GEMINI_API_KEY"),
        gemini_models=_parse_gemini_models(),
        symbol=os.getenv("SYMBOL", "BTCUSDT").strip().upper(),
        interval=os.getenv("INTERVAL", "15m").strip(),
        klines_limit=_int("KLINES_LIMIT", 50),
        loop_interval_sec=_int("LOOP_INTERVAL_SEC", 900),
        quote_order_qty=_float("QUOTE_ORDER_QTY", 50.0),
        trade_percent=_float("TRADE_PERCENT", 0.0),
        max_trades_per_day=_int("MAX_TRADES_PER_DAY", 10),
        cooldown_minutes=_int("COOLDOWN_MINUTES", 30),
        min_confidence=_float("MIN_CONFIDENCE", 0.6),
        execute_orders=_bool("EXECUTE_ORDERS", True),
        logs_dir=os.getenv("LOGS_DIR", "logs").strip(),
    )
