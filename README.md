# Bot de trading IA — Binance Spot Testnet

Bot en Python que opera en **Binance Spot Testnet** (dinero ficticio) y obtiene señales `BUY` / `SELL` / `HOLD` desde **Google Gemini**.

> Prototipo educativo. No garantiza rentabilidad. No uses keys de producción sin backtesting.

## Requisitos

- Python 3.11+
- Cuenta en [Binance Spot Testnet](https://testnet.binance.vision/) (login con GitHub)
- API key de [Google AI Studio](https://aistudio.google.com/apikey)

## Instalación

```powershell
cd trading
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus claves de **testnet** y Gemini.

## Binance Testnet: paso a paso (virtual y gratuito)

Sí: **es dinero ficticio y no pagas** por operar en testnet. No es tu cuenta real de Binance.com.

| Qué | Testnet | Cuenta real Binance |
|-----|---------|---------------------|
| Dinero | USDT/BTC de prueba | Tu dinero real |
| Registro | GitHub en testnet.binance.vision | binance.com + KYC |
| API keys | Solo válidas en testnet | Solo válidas en producción |
| Coste | Gratis | Comisiones reales |

### Pasos

1. Abre https://testnet.binance.vision/
2. Pulsa **Log in with GitHub** (sí, GitHub primero; no hace falta cuenta Binance real).
3. Autoriza la app de testnet en GitHub.
4. En el panel de testnet, genera **API Key** + **Secret** (tipo HMAC, el más simple).
5. Copia ambos a `.env` (`BINANCE_API_KEY`, `BINANCE_API_SECRET`).
6. Deja `BINANCE_BASE_URL=https://testnet.binance.vision`.
7. En testnet suele haber un botón para **recargar saldo ficticio** (faucet) si no tienes USDT/BTC de prueba.
8. Prueba: `python bot.py status` — debe mostrar precio y balances sin error.

Las keys de testnet **no funcionan** en `api.binance.com` (producción).

## Configuración de Gemini (capa gratuita)

1. Crea una API key en https://aistudio.google.com/apikey (gratis con límites diarios).
2. Añade `GEMINI_API_KEY` en `.env`.
3. El bot prueba varios modelos en orden; si uno falla (no disponible en free tier, cuota, etc.), pasa al siguiente.

Orden por defecto (editable con `GEMINI_MODELS` en `.env`):

- `gemini-3.5-flash`
- `gemini-3.1-flash-lite-preview`
- `gemini-3-flash-preview`
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash`

Opcional: `GEMINI_MODEL=gemini-2.5-flash` se intenta **primero**, luego el resto de la lista.

En la razón de la señal verás qué modelo respondió, p. ej. `[gemini-2.5-flash-lite] ...`.

## Uso

```powershell
# Ver precio y balances (sin IA ni órdenes)
python bot.py status

# Una evaluación: Gemini + riesgo; ejecuta si EXECUTE_ORDERS=true
python bot.py once

# Solo señal, sin órdenes
python bot.py once --dry-run

# Bucle cada LOOP_INTERVAL_SEC (default 900 s = 15 min)
python bot.py run
```

Para **solo analizar** sin operar, pon en `.env`:

```
EXECUTE_ORDERS=false
```

## Variables de entorno principales

| Variable | Descripción |
|----------|-------------|
| `SYMBOL` | Par, ej. `BTCUSDT` |
| `INTERVAL` | Velas para el prompt, ej. `15m` |
| `QUOTE_ORDER_QTY` | USDT ficticios por compra MARKET |
| `MAX_TRADES_PER_DAY` | Límite diario |
| `COOLDOWN_MINUTES` | Espera entre trades |
| `MIN_CONFIDENCE` | Por debajo → HOLD |
| `EXECUTE_ORDERS` | `true` / `false` |
| `GEMINI_MODEL` | Modelo preferido (se prueba primero) |
| `GEMINI_MODELS` | Lista separada por comas (fallback) |

## Logs

- `logs/decisions.jsonl` — cada señal de Gemini
- `logs/trades.jsonl` — órdenes ejecutadas

## Arquitectura

```
bot.py           → CLI (status / once / run)
binance_client.py → Testnet: precio, velas, balances, órdenes MARKET
gemini_advisor.py → Señal JSON BUY|SELL|HOLD
risk.py          → Cooldown, límites, tamaño de posición
config.py        → Carga .env y valida URL testnet
```

## Flujo de prueba recomendado

1. `python bot.py status` — comprueba conexión testnet
2. `EXECUTE_ORDERS=false` → `python bot.py once` — prueba Gemini
3. `EXECUTE_ORDERS=true` → `python bot.py once --dry-run` — revisa riesgo
4. `python bot.py once` — orden mínima en testnet
5. `python bot.py run` — bucle continuo

## Limitaciones

- El LLM es lento y tiene coste por llamada; intervalo ≥ 15 min recomendado
- Testnet puede diferir del mercado real
- Órdenes **MARKET** únicamente en v1
- El bot aborta si `BINANCE_BASE_URL` no contiene `testnet`

## Seguridad

- No subas `.env` a git
- Revoca keys si se filtran
- No cambies a producción sin entender el riesgo
