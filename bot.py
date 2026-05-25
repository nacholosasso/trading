#!/usr/bin/env python3
"""Binance Spot Testnet trading bot with Gemini signals."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from binance_client import BinanceTestnetClient
from config import Config, load_config
from gemini_advisor import GeminiAdvisor, TradingSignal
from risk import TradeDecision, evaluate_trade


def _log_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_status(config: Config, client: BinanceTestnetClient) -> int:
    price = client.get_ticker_price()
    balances = client.get_balances()
    print(f"Symbol: {config.symbol}")
    print(f"Price:  {price}")
    print("Balances:")
    for asset, data in sorted(balances.items()):
        print(f"  {asset}: free={data['free']:.8f} locked={data['locked']:.8f}")
    return 0


def _fetch_context(config: Config, client: BinanceTestnetClient) -> tuple[float, Any, dict[str, Any]]:
    price = client.get_ticker_price()
    klines = client.get_klines_df()
    balances = client.get_balances()
    return price, klines, balances


def _log_decision(config: Config, price: float, signal: TradingSignal, trade: TradeDecision | None) -> None:
    record: dict[str, Any] = {
        "timestamp": _now_iso(),
        "symbol": config.symbol,
        "price": price,
        "action": signal.action,
        "confidence": signal.confidence,
        "reason": signal.reason,
    }
    if trade:
        record["trade_allowed"] = trade.allowed
        record["trade_reason"] = trade.reason
    _log_jsonl(Path(config.logs_dir) / "decisions.jsonl", record)


def _execute_trade(
    config: Config,
    client: BinanceTestnetClient,
    signal: TradingSignal,
    trade: TradeDecision,
) -> dict[str, Any] | None:
    if not trade.allowed:
        return None

    if signal.action == "BUY" and trade.quote_qty:
        return client.place_market_buy_quote(trade.quote_qty)

    if signal.action == "SELL" and trade.sell_qty:
        return client.place_market_sell(trade.sell_qty)

    return None


def run_cycle(config: Config, client: BinanceTestnetClient, advisor: GeminiAdvisor, dry_run: bool = False) -> int:
    price, klines, balances = _fetch_context(config, client)
    signal = advisor.get_signal(price, klines, balances)
    min_qty = client.get_min_qty()

    trade = evaluate_trade(
        config,
        signal,
        balances,
        config.base_asset,
        config.quote_asset,
        min_qty,
    )

    print(f"\n[{_now_iso()}] {config.symbol} @ {price}")
    print(f"Signal: {signal.action} (confidence={signal.confidence:.2f})")
    print(f"Reason: {signal.reason}")
    print(f"Trade:  {'ALLOWED' if trade.allowed else 'BLOCKED'} — {trade.reason}")

    _log_decision(config, price, signal, trade)

    if dry_run or not config.execute_orders:
        if not config.execute_orders:
            print("(EXECUTE_ORDERS=false, skipping order placement)")
        return 0

    if not trade.allowed:
        return 0

    try:
        order = _execute_trade(config, client, signal, trade)
        if order:
            print(f"Order placed: orderId={order.get('orderId')} status={order.get('status')}")
            _log_jsonl(
                Path(config.logs_dir) / "trades.jsonl",
                {
                    "timestamp": _now_iso(),
                    "symbol": config.symbol,
                    "side": signal.action,
                    "price": price,
                    "order": order,
                    "signal_reason": signal.reason,
                },
            )
    except Exception as exc:
        print(f"Order failed: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_once(config: Config, dry_run: bool) -> int:
    client = BinanceTestnetClient(config)
    advisor = GeminiAdvisor(config)
    return run_cycle(config, client, advisor, dry_run=dry_run)


def cmd_run(config: Config, dry_run: bool) -> int:
    client = BinanceTestnetClient(config)
    advisor = GeminiAdvisor(config)
    print(f"Starting bot on {config.symbol} (interval={config.loop_interval_sec}s)")
    print(f"Testnet: {config.binance_base_url}")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_cycle(config, client, advisor, dry_run=dry_run)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
        except Exception as exc:
            print(f"Cycle error: {exc}", file=sys.stderr)

        time.sleep(config.loop_interval_sec)


def main() -> int:
    parser = argparse.ArgumentParser(description="Binance Spot Testnet bot with Gemini signals")
    parser.add_argument("command", choices=["status", "once", "run"], help="Command to run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate signal and risk but never place orders",
    )
    args = parser.parse_args()

    config = load_config()
    dry_run = args.dry_run

    if args.command == "status":
        client = BinanceTestnetClient(config)
        return cmd_status(config, client)
    if args.command == "once":
        return cmd_once(config, dry_run)
    if args.command == "run":
        return cmd_run(config, dry_run)
    return 1


if __name__ == "__main__":
    sys.exit(main())
