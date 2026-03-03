# exec-engine

Minimal execution engine — uniform order management across any broker API.

`exec-engine` provides a single interface (`ExecEngine`) for submitting, modifying, cancelling orders and querying positions/account state. You bring the broker adapter; everything else stays the same.

## Install

```bash
# Core library (zero dependencies)
pip install -e .

# With dev/test tools
pip install -e ".[dev]"
```

## Quick Start

```python
from exec_engine import ExecEngine, Order, Side, OrderType

# 1. Import your adapter (you build this — see "Adding a New Broker" below)
from exec_engine.adapters.my_broker import MyBrokerAdapter

# 2. Create adapter with your credentials
broker = MyBrokerAdapter(api_key="...", api_secret="...", base_url="...", account_id="...")

# 3. Create engine and connect
engine = ExecEngine(broker)
engine.connect()

# 4. Submit orders via convenience methods
fill = engine.market_buy("EURUSD", 0.5, sl=1.0700, tp=1.0900)
print(f"Filled @ {fill.avg_price}")

# 5. Or build an Order for full control
order = Order(
    symbol="GBPUSD",
    side=Side.SELL,
    order_type=OrderType.LIMIT,
    quantity=1.0,
    price=1.2650,
    stop_loss=1.2700,
    take_profit=1.2550,
    comment="limit entry",
    magic=42,
)
fill = engine.submit(order)

# 6. Query positions and account
for pos in engine.positions():
    print(f"{pos.symbol} {pos.side.value} {pos.quantity} @ {pos.entry_price}")

acct = engine.account()
print(f"Equity: {acct.equity}")

# 7. Close and disconnect
engine.close_all()
engine.disconnect()
```

## Adding a New Broker

1. Copy the template:

```bash
cp exec_engine/adapters/_template.py exec_engine/adapters/my_broker.py
```

2. Rename the class from `MyBrokerAdapter` to match your broker (e.g. `TopstepAdapter`).

3. Implement every method — each one has a docstring and step-by-step comments explaining what to do.

4. Use it:

```python
from exec_engine.adapters.my_broker import TopstepAdapter

broker = TopstepAdapter(api_key="...", account_id="...")
engine = ExecEngine(broker)
```

**Swapping brokers requires changing only the adapter line** — zero changes to order logic or strategy code:

```python
# broker = TopstepAdapter(...)     # OLD
broker = AlpacaAdapter(...)         # NEW — that's it
engine = ExecEngine(broker)
```

## API Reference — ExecEngine

| Method | Description |
|---|---|
| `connect()` | Connect to the broker, log account info |
| `disconnect()` | Disconnect from the broker |
| `submit(order)` | Submit an `Order`, return a `Fill` |
| `cancel(broker_order_id)` | Cancel an open order, return `True`/`False` |
| `modify(broker_order_id, **kwargs)` | Modify an order (price, sl, tp, quantity) |
| `positions(symbol=None)` | List open positions |
| `open_orders(symbol=None)` | List open/pending orders |
| `account()` | Get current account state |
| `close(ticket)` | Close a single position by ticket |
| `close_all(symbol=None)` | Close all positions (optionally filtered) |
| `flatten(symbol)` | Alias for `close_all(symbol)` |

## Convenience Methods

| Method | Side | Type |
|---|---|---|
| `market_buy(symbol, qty, sl, tp, comment, magic, **meta)` | BUY | MARKET |
| `market_sell(symbol, qty, sl, tp, comment, magic, **meta)` | SELL | MARKET |
| `limit_buy(symbol, qty, price, sl, tp, comment, magic, **meta)` | BUY | LIMIT |
| `limit_sell(symbol, qty, price, sl, tp, comment, magic, **meta)` | SELL | LIMIT |
| `stop_buy(symbol, qty, price, sl, tp, comment, magic, **meta)` | BUY | STOP |
| `stop_sell(symbol, qty, price, sl, tp, comment, magic, **meta)` | SELL | STOP |

All convenience methods construct an `Order` internally and call `submit()`. Extra `**meta` keyword arguments are stored in `Order.meta`.

## Data Types

- **`Order`** — what you want to execute (symbol, side, type, qty, price, SL/TP, etc.)
- **`Fill`** — what the broker did (status, filled qty, avg price, broker order ID)
- **`Position`** — an open position (symbol, side, qty, entry price, P&L)
- **`Account`** — account state (balance, equity, margin, currency)
- **`Side`** — `BUY` / `SELL`
- **`OrderType`** — `MARKET` / `LIMIT` / `STOP` / `STOP_LIMIT`
- **`OrderStatus`** — `PENDING` / `SUBMITTED` / `FILLED` / `PARTIAL` / `CANCELLED` / `REJECTED` / `EXPIRED`

## Running Tests

```bash
pytest tests/ -v
```
