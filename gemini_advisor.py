"""Gemini-based trading signal advisor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd
from google import genai
from google.genai import types

from config import Config


@dataclass
class TradingSignal:
    action: str  # BUY, SELL, HOLD
    confidence: float
    reason: str
    suggested_quote_qty: float | None = None

    @property
    def is_hold(self) -> bool:
        return self.action == "HOLD"


SIGNAL_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["action", "confidence", "reason"],
    properties={
        "action": types.Schema(
            type=types.Type.STRING,
            enum=["BUY", "SELL", "HOLD"],
        ),
        "confidence": types.Schema(type=types.Type.NUMBER),
        "reason": types.Schema(type=types.Type.STRING),
        "suggested_quote_qty": types.Schema(type=types.Type.NUMBER, nullable=True),
    },
)


def _klines_to_text(df: pd.DataFrame, max_rows: int = 20) -> str:
    tail = df.tail(max_rows)[["open_time", "open", "high", "low", "close", "volume"]]
    return tail.to_string(index=False)


def _balances_to_text(balances: dict[str, Any]) -> str:
    lines = []
    for asset, data in sorted(balances.items()):
        lines.append(f"{asset}: free={data['free']:.8f}, locked={data['locked']:.8f}")
    return "\n".join(lines) if lines else "(no balances)"


class GeminiAdvisor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = genai.Client(api_key=config.gemini_api_key)
        self._last_model_used: str | None = None

    @property
    def last_model_used(self) -> str | None:
        return self._last_model_used

    def _generate_with_fallback(self, prompt: str) -> tuple[dict[str, Any], str]:
        errors: list[str] = []
        for model in self.config.gemini_models:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=SIGNAL_SCHEMA,
                    ),
                )
                raw = response.text or "{}"
                data = json.loads(raw)
                self._last_model_used = model
                return data, model
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                continue
        raise RuntimeError("; ".join(errors) if errors else "No Gemini models configured")

    def get_signal(
        self,
        price: float,
        klines_df: pd.DataFrame,
        balances: dict[str, Any],
        symbol: str | None = None,
    ) -> TradingSignal:
        symbol = symbol or self.config.symbol
        prompt = f"""You are a cautious crypto trading assistant analyzing {symbol} on Binance Spot TESTNET (paper money only).

Current price: {price}
Interval: {self.config.interval}

Recent OHLCV candles:
{_klines_to_text(klines_df)}

Account balances:
{_balances_to_text(balances)}

Rules:
- Respond with a single trading decision for the next interval.
- Prefer HOLD when the trend is unclear or risk is high.
- BUY only if you see a reasonable entry; SELL only if holding base asset and exit makes sense.
- This is educational testnet trading, not financial advice.

Return JSON with: action (BUY|SELL|HOLD), confidence (0.0-1.0), reason (brief), suggested_quote_qty (optional USDT amount for BUY, null otherwise).
"""

        try:
            data, model = self._generate_with_fallback(prompt)
            signal = self._parse_signal(data)
            return TradingSignal(
                action=signal.action,
                confidence=signal.confidence,
                reason=f"[{model}] {signal.reason}",
                suggested_quote_qty=signal.suggested_quote_qty,
            )
        except Exception as exc:
            self._last_model_used = None
            return TradingSignal(
                action="HOLD",
                confidence=0.0,
                reason=f"Gemini error (all models failed), HOLD: {exc}",
            )

    def _parse_signal(self, data: dict[str, Any]) -> TradingSignal:
        action = str(data.get("action", "HOLD")).upper()
        if action not in ("BUY", "SELL", "HOLD"):
            action = "HOLD"

        try:
            confidence = float(data.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        reason = str(data.get("reason", ""))[:500]
        suggested = data.get("suggested_quote_qty")
        suggested_qty: float | None = None
        if suggested is not None:
            try:
                suggested_qty = float(suggested)
            except (TypeError, ValueError):
                suggested_qty = None

        if confidence < self.config.min_confidence:
            return TradingSignal(
                action="HOLD",
                confidence=confidence,
                reason=f"Low confidence ({confidence:.2f}): {reason}",
                suggested_quote_qty=suggested_qty,
            )

        return TradingSignal(
            action=action,
            confidence=confidence,
            reason=reason,
            suggested_quote_qty=suggested_qty,
        )
