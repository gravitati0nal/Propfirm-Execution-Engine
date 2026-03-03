"""TopstepX (ProjectX) broker adapter.

Implements the BrokerAdapter interface against the ProjectX Gateway REST API
at api.thefuturesdesk.projectx.com.  All endpoints are POST-based and require
a JWT bearer token obtained via /api/Auth/loginKey.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from exec_engine.adapter import BrokerAdapter
from exec_engine.exceptions import BrokerError, ConnectionError, OrderError
from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
)

logger = logging.getLogger("exec_engine.topstep")

_BASE_URL = "https://api.topstepx.com"

_SIDE_MAP = {Side.BUY: 0, Side.SELL: 1}        # 0=Bid(Buy), 1=Ask(Sell)
_SIDE_REVERSE = {0: Side.BUY, 1: Side.SELL}

_ORDER_TYPE_MAP = {
    OrderType.MARKET: 2,      # Market
    OrderType.LIMIT: 1,       # Limit
    OrderType.STOP: 4,        # Stop
    OrderType.STOP_LIMIT: 3,  # StopLimit
}

_PX_STATUS_MAP = {
    1: OrderStatus.SUBMITTED,   # Open
    2: OrderStatus.FILLED,      # Filled
    3: OrderStatus.CANCELLED,   # Cancelled
    4: OrderStatus.EXPIRED,     # Expired
    5: OrderStatus.REJECTED,    # Rejected
    6: OrderStatus.PENDING,     # Pending
}

_POS_TYPE_MAP = {1: Side.BUY, 2: Side.SELL}  # Long / Short


class TopstepAdapter(BrokerAdapter):
    """Adapter for TopstepX via the ProjectX Gateway REST API."""

    def __init__(
        self,
        api_key: str,
        username: str,
        account_id: Optional[int] = None,
        base_url: str = _BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._username = username
        self._account_id = account_id
        self._base_url = base_url.rstrip("/")
        self._connected = False
        self._token: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._contract_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Account discovery (pre-connect)
    # ------------------------------------------------------------------

    @classmethod
    def list_accounts(
        cls,
        api_key: str,
        username: str,
        base_url: str = _BASE_URL,
    ) -> list[dict]:
        """Authenticate and return all available TopstepX accounts.

        Call this *before* constructing the adapter to discover which
        ``account_id`` to pass to the constructor.

        Returns a list of dicts, each with keys: id, name, balance,
        canTrade, isVisible.

        Raises:
            ConnectionError: if authentication fails.
            BrokerError: if the account search request fails.
        """
        base_url = base_url.rstrip("/")
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})

        try:
            resp = session.post(
                f"{base_url}/api/Auth/loginKey",
                json={"apiKey": api_key, "userName": username},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            session.close()
            raise ConnectionError(f"Auth request failed: {exc}") from exc

        if not data.get("success"):
            session.close()
            err_msg = data.get("errorMessage") or f"errorCode={data.get('errorCode', '?')}"
            raise ConnectionError(f"Authentication failed: {err_msg}")

        session.headers["Authorization"] = f"Bearer {data['token']}"

        try:
            resp = session.post(
                f"{base_url}/api/Account/search",
                json={"onlyActiveAccounts": True},
                timeout=30,
            )
            resp.raise_for_status()
            acct_data = resp.json()
        except requests.exceptions.RequestException as exc:
            raise BrokerError(f"Account search failed: {exc}") from exc
        finally:
            session.close()

        if not acct_data.get("success"):
            raise BrokerError(
                f"Account search failed: {acct_data.get('errorMessage', 'unknown error')}",
                raw_response=acct_data,
            )

        return acct_data.get("accounts", [])

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        self._authenticate()

        if self._account_id is None:
            data = self._request("/api/Account/search", {"onlyActiveAccounts": True})
            accounts = data.get("accounts", [])
            tradable = [a for a in accounts if a.get("canTrade")]
            if not tradable:
                raise ConnectionError("No active tradable accounts found")
            self._account_id = tradable[0]["id"]
            logger.info("Auto-selected account %s (%s)", self._account_id, tradable[0].get("name"))

        self._connected = True
        logger.info("Connected to TopstepX (account=%s)", self._account_id)

    def disconnect(self) -> None:
        self._session.headers.pop("Authorization", None)
        self._token = None
        self._connected = False
        self._contract_cache.clear()
        logger.info("Disconnected from TopstepX")

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    def submit(self, order: Order) -> Fill:
        contract = self._resolve_symbol(order.symbol)
        contract_id = contract["id"]
        size = int(order.quantity)

        payload: dict = {
            "accountId": self._account_id,
            "contractId": contract_id,
            "type": _ORDER_TYPE_MAP[order.order_type],
            "side": _SIDE_MAP[order.side],
            "size": size,
            "limitPrice": None,
            "stopPrice": None,
            "trailPrice": None,
            "customTag": order.comment or None,
        }

        if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            payload["limitPrice"] = order.price
        if order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            payload["stopPrice"] = order.price

        tick_size = contract.get("tickSize", 1)
        if order.stop_loss is not None:
            sl_ticks = max(1, int(abs(order.stop_loss - (order.price or 0)) / tick_size))
            payload["stopLossBracket"] = {"ticks": sl_ticks, "type": 4}
        if order.take_profit is not None:
            tp_ticks = max(1, int(abs(order.take_profit - (order.price or 0)) / tick_size))
            payload["takeProfitBracket"] = {"ticks": tp_ticks, "type": 1}

        data = self._request("/api/Order/place", payload)

        if not data.get("success"):
            return Fill(
                order_id=order.id,
                broker_order_id="",
                status=OrderStatus.REJECTED,
                symbol=order.symbol,
                side=order.side,
                filled_qty=0.0,
                avg_price=0.0,
                message=data.get("errorMessage", "Unknown error"),
                raw=data,
            )

        broker_order_id = str(data["orderId"])

        filled_qty = 0.0
        avg_price = 0.0
        status = OrderStatus.SUBMITTED

        if order.order_type == OrderType.MARKET:
            time.sleep(0.3)
            fill_data = self._request("/api/Order/search", {
                "accountId": self._account_id,
                "startTimestamp": order.meta.get(
                    "_submit_ts",
                    "2020-01-01T00:00:00Z",
                ),
            })
            for o in fill_data.get("orders", []):
                if str(o.get("id")) == broker_order_id:
                    status = _PX_STATUS_MAP.get(o.get("status", 0), OrderStatus.SUBMITTED)
                    filled_qty = float(o.get("fillVolume", 0))
                    avg_price = float(o.get("filledPrice") or 0)
                    break

        return Fill(
            order_id=order.id,
            broker_order_id=broker_order_id,
            status=status,
            symbol=order.symbol,
            side=order.side,
            filled_qty=filled_qty,
            avg_price=avg_price,
            raw=data,
        )

    def cancel(self, broker_order_id: str) -> bool:
        data = self._request("/api/Order/cancel", {
            "accountId": self._account_id,
            "orderId": int(broker_order_id),
        })
        return data.get("success", False)

    def modify(
        self,
        broker_order_id: str,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        quantity: Optional[float] = None,
    ) -> Fill:
        payload: dict = {
            "accountId": self._account_id,
            "orderId": int(broker_order_id),
        }
        if quantity is not None:
            payload["size"] = int(quantity)
        if price is not None:
            payload["limitPrice"] = price
        if sl is not None:
            payload["stopPrice"] = sl

        data = self._request("/api/Order/modify", payload)

        if not data.get("success"):
            return Fill(
                order_id="",
                broker_order_id=broker_order_id,
                status=OrderStatus.REJECTED,
                symbol="",
                side=Side.BUY,
                filled_qty=0.0,
                avg_price=0.0,
                message=data.get("errorMessage", "Modify failed"),
                raw=data,
            )

        return Fill(
            order_id="",
            broker_order_id=broker_order_id,
            status=OrderStatus.SUBMITTED,
            symbol="",
            side=Side.BUY,
            filled_qty=0.0,
            avg_price=0.0,
            raw=data,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def positions(self, symbol: Optional[str] = None) -> list[Position]:
        data = self._request("/api/Position/searchOpen", {
            "accountId": self._account_id,
        })
        result: list[Position] = []
        for raw in data.get("positions", []):
            side = _POS_TYPE_MAP.get(raw.get("type", 0), Side.BUY)
            contract_id = raw.get("contractId", "")
            result.append(Position(
                symbol=contract_id,
                side=side,
                quantity=float(raw.get("size", 0)),
                entry_price=float(raw.get("averagePrice", 0)),
                ticket=contract_id,
            ))

        if symbol:
            contract = self._resolve_symbol(symbol)
            cid = contract["id"]
            result = [p for p in result if p.symbol == cid]

        return result

    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        data = self._request("/api/Order/searchOpen", {
            "accountId": self._account_id,
        })
        orders = data.get("orders", [])

        if symbol:
            contract = self._resolve_symbol(symbol)
            cid = contract["id"]
            orders = [o for o in orders if o.get("contractId") == cid]

        return orders

    def account(self) -> Account:
        data = self._request("/api/Account/search", {"onlyActiveAccounts": True})
        for acct in data.get("accounts", []):
            if acct.get("id") == self._account_id:
                balance = float(acct.get("balance", 0))
                return Account(
                    balance=balance,
                    equity=balance,
                    margin_used=0.0,
                    margin_free=balance,
                    currency="USD",
                    account_id=str(self._account_id),
                )

        raise BrokerError(
            f"Account {self._account_id} not found",
            raw_response=data,
        )

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def close_position(self, ticket: str) -> Fill:
        """Close a position by submitting an opposite-side market order."""
        open_positions = self.positions()
        target = None
        for pos in open_positions:
            if pos.ticket == ticket:
                target = pos
                break

        if target is None:
            raise OrderError(f"No open position with ticket {ticket}")

        opposite_side = Side.SELL if target.side == Side.BUY else Side.BUY
        close_order = Order(
            symbol=target.symbol,
            side=opposite_side,
            order_type=OrderType.MARKET,
            quantity=target.quantity,
        )
        close_order.meta["_is_close"] = True
        return self.submit(close_order)

    def close_all(self, symbol: Optional[str] = None) -> list[Fill]:
        fills: list[Fill] = []
        for pos in self.positions(symbol):
            fills.append(self.close_position(pos.ticket))
        return fills

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "TopstepX"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        try:
            resp = self._session.post(
                f"{self._base_url}/api/Auth/loginKey",
                json={"apiKey": self._api_key, "userName": self._username},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Auth request failed: {exc}") from exc

        if not data.get("success"):
            err_msg = data.get("errorMessage") or f"errorCode={data.get('errorCode', '?')}"
            raise ConnectionError(f"Authentication failed: {err_msg}")

        self._token = data["token"]
        self._session.headers["Authorization"] = f"Bearer {self._token}"
        logger.info("Authenticated with TopstepX")

    def _request(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.post(url, json=payload, timeout=30)
        except requests.exceptions.RequestException as exc:
            raise BrokerError(f"Request to {path} failed: {exc}") from exc

        if resp.status_code == 401:
            logger.warning("Got 401, re-authenticating...")
            self._authenticate()
            try:
                resp = self._session.post(url, json=payload, timeout=30)
            except requests.exceptions.RequestException as exc:
                raise BrokerError(f"Retry request to {path} failed: {exc}") from exc

        if resp.status_code >= 400:
            raise BrokerError(
                f"{path} returned HTTP {resp.status_code}: {resp.text}",
                raw_response=resp.text,
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise BrokerError(f"Invalid JSON from {path}", raw_response=resp.text) from exc

    def _resolve_symbol(self, symbol: str) -> dict:
        """Map a user-friendly symbol (e.g. 'NQ', 'ES') to a ProjectX contract dict.

        Uses /api/Contract/search and caches results for the session.
        If ``symbol`` already looks like a full contract ID (starts with 'CON.'),
        it is passed through to searchById instead.
        """
        if symbol in self._contract_cache:
            return self._contract_cache[symbol]

        if symbol.startswith("CON."):
            data = self._request("/api/Contract/searchById", {"contractId": symbol})
            contract = data.get("contract")
            if contract:
                self._contract_cache[symbol] = contract
                return contract
            raise OrderError(f"Contract ID {symbol} not found")

        data = self._request("/api/Contract/search", {
            "searchText": symbol,
            "live": False,
        })
        contracts = data.get("contracts", [])
        active = [c for c in contracts if c.get("activeContract")]
        if not active:
            raise OrderError(f"No active contract found for symbol '{symbol}'")

        contract = active[0]
        self._contract_cache[symbol] = contract
        logger.info("Resolved '%s' -> %s (%s)", symbol, contract["id"], contract.get("description", ""))
        return contract


# ======================================================================
# SMOKE TEST — run directly to verify live connectivity
#   python -m exec_engine.adapters.topstep
# ======================================================================

if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

    api_key = os.environ.get("TOPSTEP_API_KEY", "")
    username = os.environ.get("TOPSTEP_USERNAME", "")
    if not api_key:
        print("Set TOPSTEP_API_KEY and TOPSTEP_USERNAME env vars first.")
        raise SystemExit(1)

    from exec_engine import ExecEngine

    print("[0] Discovering accounts...")
    accounts = TopstepAdapter.list_accounts(api_key=api_key, username=username)
    for a in accounts:
        tradable = "tradable" if a.get("canTrade") else "locked"
        print(f"    id={a['id']}  name={a.get('name', '?')}  balance={a.get('balance', 0)}  ({tradable})")
    if not accounts:
        print("    (no accounts found)")
        raise SystemExit(1)

    chosen = accounts[0]["id"]
    print(f"    -> Using account {chosen}\n")

    broker = TopstepAdapter(api_key=api_key, username=username, account_id=chosen)
    engine = ExecEngine(broker)

    print("[1] Connecting...")
    engine.connect()
    print(f"    Connected! account_id={broker._account_id}\n")

    print("[2] Account info...")
    acct = engine.account()
    print(f"    Balance:  {acct.balance}")
    print(f"    Currency: {acct.currency}\n")

    print("[3] Resolving MNQ contract...")
    contract = broker._resolve_symbol("MNQ")
    print(f"    {contract['id']} — {contract.get('description', '')}\n")

    print("[4] Open positions...")
    for pos in engine.positions():
        print(f"    {pos.symbol} {pos.side.value} {pos.quantity} @ {pos.entry_price}")
    if not engine.positions():
        print("    (none)\n")

    print("[5] Open orders...")
    for o in engine.open_orders():
        print(f"    id={o.get('id')}  contract={o.get('contractId')}  status={o.get('status')}")
    if not engine.open_orders():
        print("    (none)\n")

    print("[6] Disconnecting...")
    engine.disconnect()
    print("    Done!")
