"""Risk management and trade eligibility checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import Config
from gemini_advisor import TradingSignal


@dataclass
class TradeDecision:
    allowed: bool
    reason: str
    quote_qty: float | None = None
    sell_qty: float | None = None


def _logs_path(config: Config, filename: str) -> Path:
    path = Path(config.logs_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path / filename


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def count_trades_today(config: Config) -> int:
    path = _logs_path(config, "trades.jsonl")
    today = datetime.now(timezone.utc).date()
    count = 0
    for row in _read_jsonl(path):
        ts = row.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.date() == today:
                count += 1
        except ValueError:
            continue
    return count


def last_trade_time(config: Config) -> datetime | None:
    path = _logs_path(config, "trades.jsonl")
    rows = _read_jsonl(path)
    if not rows:
        return None
    last = rows[-1].get("timestamp", "")
    try:
        return datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_in_cooldown(config: Config) -> bool:
    last = last_trade_time(config)
    if last is None:
        return False
    elapsed = datetime.now(timezone.utc) - last
    return elapsed < timedelta(minutes=config.cooldown_minutes)


def compute_quote_qty(config: Config, signal: TradingSignal, usdt_free: float) -> float:
    if signal.suggested_quote_qty and signal.suggested_quote_qty > 0:
        qty = signal.suggested_quote_qty
    elif config.trade_percent > 0:
        qty = usdt_free * (config.trade_percent / 100.0)
    else:
        qty = config.quote_order_qty
    return min(qty, usdt_free * 0.99)


def evaluate_trade(
    config: Config,
    signal: TradingSignal,
    balances: dict[str, Any],
    base_asset: str,
    quote_asset: str,
    min_base_qty: float,
) -> TradeDecision:
    if signal.is_hold:
        return TradeDecision(False, "Signal is HOLD")

    if is_in_cooldown(config):
        return TradeDecision(False, f"Cooldown active ({config.cooldown_minutes} min)")

    if count_trades_today(config) >= config.max_trades_per_day:
        return TradeDecision(False, f"Max trades per day reached ({config.max_trades_per_day})")

    quote_free = float(balances.get(quote_asset, {}).get("free", 0))
    base_free = float(balances.get(base_asset, {}).get("free", 0))

    if signal.action == "BUY":
        quote_qty = compute_quote_qty(config, signal, quote_free)
        if quote_qty < 10:
            return TradeDecision(False, f"Insufficient {quote_asset} (need ~10+, have {quote_free:.2f})")
        return TradeDecision(True, "BUY approved", quote_qty=quote_qty)

    if signal.action == "SELL":
        if base_free < min_base_qty:
            return TradeDecision(
                False,
                f"Insufficient {base_asset} (have {base_free:.8f}, min {min_base_qty})",
            )
        sell_qty = base_free * 0.99
        return TradeDecision(True, "SELL approved", sell_qty=sell_qty)

    return TradeDecision(False, f"Unknown action {signal.action}")
