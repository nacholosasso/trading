"""Binance Spot Testnet API wrapper."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

from config import Config


class BinanceTestnetClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = Client(
            config.binance_api_key,
            config.binance_api_secret,
            testnet=True,
        )
        api_url = f"{config.binance_base_url.rstrip('/')}/api"
        self._client.API_URL = api_url

    def get_ticker_price(self, symbol: str | None = None) -> float:
        symbol = symbol or self.config.symbol
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def get_klines_df(self, symbol: str | None = None, interval: str | None = None, limit: int | None = None) -> pd.DataFrame:
        symbol = symbol or self.config.symbol
        interval = interval or self.config.interval
        limit = limit or self.config.klines_limit
        raw = self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(
            raw,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df

    def get_balances(self) -> dict[str, float]:
        account = self._client.get_account()
        balances: dict[str, float] = {}
        for entry in account.get("balances", []):
            free = float(entry.get("free", 0))
            locked = float(entry.get("locked", 0))
            total = free + locked
            if total > 0:
                balances[entry["asset"]] = {"free": free, "locked": locked, "total": total}
        return balances

    def get_balance_free(self, asset: str) -> float:
        balances = self.get_balances()
        if asset not in balances:
            return 0.0
        return float(balances[asset]["free"])

    def get_symbol_filters(self, symbol: str | None = None) -> dict[str, Any]:
        symbol = symbol or self.config.symbol
        info = self._client.get_symbol_info(symbol=symbol)
        if not info:
            raise BinanceAPIException(None, 400, f"Symbol {symbol} not found")
        filters: dict[str, Any] = {}
        for f in info.get("filters", []):
            filters[f["filterType"]] = f
        return filters

    def _round_step(self, value: float, step: str) -> float:
        step_dec = Decimal(step)
        if step_dec == 0:
            return value
        quantized = Decimal(str(value)).quantize(step_dec, rounding="ROUND_DOWN")
        return float(quantized)

    def round_quantity(self, quantity: float, symbol: str | None = None) -> float:
        filters = self.get_symbol_filters(symbol)
        lot = filters.get("LOT_SIZE", {})
        step = lot.get("stepSize", "0.00001")
        return self._round_step(quantity, step)

    def get_min_qty(self, symbol: str | None = None) -> float:
        filters = self.get_symbol_filters(symbol)
        lot = filters.get("LOT_SIZE", {})
        return float(lot.get("minQty", 0))

    def place_market_buy_quote(self, quote_qty: float, symbol: str | None = None) -> dict[str, Any]:
        symbol = symbol or self.config.symbol
        return self._client.create_order(
            symbol=symbol,
            side=Client.SIDE_BUY,
            type=Client.ORDER_TYPE_MARKET,
            quoteOrderQty=round(quote_qty, 2),
        )

    def place_market_sell(self, quantity: float, symbol: str | None = None) -> dict[str, Any]:
        symbol = symbol or self.config.symbol
        qty = self.round_quantity(quantity, symbol)
        min_qty = self.get_min_qty(symbol)
        if qty < min_qty:
            raise ValueError(f"Quantity {qty} below minQty {min_qty} for {symbol}")
        return self._client.create_order(
            symbol=symbol,
            side=Client.SIDE_SELL,
            type=Client.ORDER_TYPE_MARKET,
            quantity=qty,
        )

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        symbol = symbol or self.config.symbol
        return self._client.get_open_orders(symbol=symbol)

    def cancel_all_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        symbol = symbol or self.config.symbol
        return self._client.cancel_open_orders(symbol=symbol)
