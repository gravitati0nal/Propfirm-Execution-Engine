"""
===========================================================================
 BROKER ADAPTER TEMPLATE
===========================================================================

 HOW TO USE THIS TEMPLATE
 -------------------------
 1.  Copy this file into the adapters/ directory with a descriptive name:
       cp _template.py my_broker.py

 2.  Rename the class from `MyBrokerAdapter` to something that matches
     your broker (e.g. `TopstepAdapter`, `IBKRAdapter`, `AlpacaAdapter`).

 3.  Fill in every method marked with `raise NotImplementedError(...)`.
     Each method has a docstring and numbered implementation steps.

 4.  If your broker uses a REST API, use the optional `_request()` helper
     at the bottom of the class. If your broker has a Python SDK or
     library, you can ignore `_request()` and call the SDK directly
     inside each method.

 5.  Install any broker-specific dependencies your adapter needs
     (e.g. `pip install requests` for REST, or the broker's own SDK).

 HOW TO REGISTER YOUR ADAPTER
 -----------------------------
 Once implemented, pass an instance of your adapter to ExecEngine:

     from exec_engine import ExecEngine
     from exec_engine.adapters.my_broker import MyBrokerAdapter

     broker = MyBrokerAdapter(
         api_key="YOUR_KEY",
         api_secret="YOUR_SECRET",
         base_url="https://api.mybroker.com",
         account_id="12345",
     )

     engine = ExecEngine(broker)
     engine.connect()

 FULL WORKFLOW EXAMPLE
 ----------------------
     from exec_engine import ExecEngine, Side, OrderType, Order
     from exec_engine.adapters.my_broker import MyBrokerAdapter

     # 1. Create adapter with your credentials
     broker = MyBrokerAdapter(
         api_key="YOUR_KEY",
         api_secret="YOUR_SECRET",
         base_url="https://api.mybroker.com",
         account_id="12345",
     )

     # 2. Create engine
     engine = ExecEngine(broker)

     # 3. Connect
     engine.connect()

     # 4. Check account
     acct = engine.account()
     print(f"Balance: {acct.balance}, Equity: {acct.equity}")

     # 5. Submit orders using convenience methods
     fill = engine.market_buy("EURUSD", 0.5, sl=1.0700, tp=1.0900)
     print(f"Fill: {fill.status.value} @ {fill.avg_price}")

     # 6. Or build an Order manually for full control
     order = Order(
         symbol="GBPUSD",
         side=Side.SELL,
         order_type=OrderType.LIMIT,
         quantity=1.0,
         price=1.2650,
         stop_loss=1.2700,
         take_profit=1.2550,
         comment="manual limit",
         magic=42,
     )
     fill = engine.submit(order)

     # 7. Query positions
     for pos in engine.positions():
         print(f"{pos.symbol} {pos.side.value} {pos.quantity} @ {pos.entry_price}")

     # 8. Close everything and disconnect
     engine.close_all()
     engine.disconnect()

 SWAPPING BROKERS
 -----------------
 To switch from one broker to another, change only the adapter
 instantiation. All strategy code, order logic, and position
 management code stays exactly the same:

     # broker = MyBrokerAdapter(...)    # OLD
     broker = OtherBrokerAdapter(...)   # NEW — that's it
     engine = ExecEngine(broker)

===========================================================================
"""

from __future__ import annotations

from typing import Optional

from exec_engine.adapter import BrokerAdapter
from exec_engine.exceptions import BrokerError, ConnectionError, OrderError
from exec_engine.types import (
    Account,
    Fill,
    Order,
    OrderStatus,
    Position,
    Side,
)


class MyBrokerAdapter(BrokerAdapter):
    """Adapter for <YOUR BROKER NAME>.  # TODO: Rename this class.

    Replace every `raise NotImplementedError(...)` with your broker's
    actual API calls. See the numbered steps in each method for guidance.
    """

    def __init__(
        self,
        api_key: str,       # TODO: Replace with your broker's connection parameters
        api_secret: str,     # TODO: Some brokers need only a token, others need key+secret
        base_url: str,       # TODO: Set your broker's API base URL (or remove for SDK-based brokers)
        account_id: str,     # TODO: Needed if the broker requires selecting an account
    ) -> None:
        """Initialize the adapter with broker credentials.

        Store credentials and set up any SDK client or HTTP session here.
        Do NOT connect to the broker yet — that happens in connect().
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._account_id = account_id
        self._connected = False

        # TODO: Initialize your broker SDK client or HTTP session here.
        # Example for REST-based brokers:
        #   self._session = requests.Session()
        #   self._session.headers.update({
        #       "Authorization": f"Bearer {self._api_key}",
        #       "Content-Type": "application/json",
        #   })
        #
        # Example for SDK-based brokers:
        #   self._client = BrokerSDK(api_key=api_key, secret=api_secret)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish a connection / session with the broker.

        Typical implementation:
          Step 1: Authenticate with the broker (login, token exchange, etc.)
          Step 2: Validate the connection (ping endpoint, fetch account info)
          Step 3: Set self._connected = True on success
          Step 4: Raise ConnectionError with a descriptive message on failure

        For REST APIs:
          - POST to a login/auth endpoint, store the session token
        For SDK-based brokers:
          - Call the SDK's connect/login method
        """
        # Step 1: Authenticate
        # response = self._request("POST", "/auth/login", json={
        #     "username": "...",
        #     "api_key": self._api_key,
        # })

        # Step 2: Validate
        # if response.get("status") != "ok":
        #     raise ConnectionError(f"Login failed: {response}")

        # Step 3: Mark connected
        # self._connected = True

        raise NotImplementedError("TODO: Implement connect() for your broker")

    def disconnect(self) -> None:
        """Cleanly disconnect / log out from the broker.

        Typical implementation:
          Step 1: Call broker's logout endpoint or SDK disconnect method
          Step 2: Clean up any resources (close HTTP session, etc.)
          Step 3: Set self._connected = False
        """
        # Step 1: Logout
        # self._request("POST", "/auth/logout")

        # Step 2: Cleanup
        # self._session.close()

        # Step 3: Mark disconnected
        # self._connected = False

        raise NotImplementedError("TODO: Implement disconnect() for your broker")

    @property
    def connected(self) -> bool:
        """Return True if the broker connection is active.

        Typical implementation:
          - Return self._connected
          - Optionally ping the broker to verify the session is still alive
        """
        return self._connected

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    def submit(self, order: Order) -> Fill:
        """Submit an order to the broker.

        Typical implementation:
          Step 1: Map exec_engine types to broker-specific values
                  - Side.BUY  -> broker's buy constant/string
                  - OrderType -> broker's order type enum/string
                  - time_in_force, slippage, etc.

          Step 2: Build the request payload / SDK call parameters
                  - Include symbol, side, quantity, price (if limit/stop),
                    stop_loss, take_profit, comment/tag, etc.

          Step 3: Send the request to the broker
                  - REST: POST /orders
                  - SDK:  client.place_order(...)

          Step 4: Parse the broker's response into a Fill object
                  - Map broker's status to OrderStatus enum
                  - Extract broker_order_id, filled quantity, average price
                  - Store raw response in Fill.raw for debugging

          Step 5: Handle errors
                  - If the broker rejects the order, return a Fill with
                    status=OrderStatus.REJECTED and the error in Fill.message
                  - For unexpected errors, raise OrderError or BrokerError

        Args:
            order: The Order to submit.

        Returns:
            Fill with the broker's response.
        """
        # --- Example implementation sketch ---
        #
        # side_map = {Side.BUY: "buy", Side.SELL: "sell"}
        # type_map = {
        #     OrderType.MARKET: "market",
        #     OrderType.LIMIT: "limit",
        #     OrderType.STOP: "stop",
        #     OrderType.STOP_LIMIT: "stop_limit",
        # }
        #
        # payload = {
        #     "symbol": order.symbol,
        #     "side": side_map[order.side],
        #     "type": type_map[order.order_type],
        #     "qty": order.quantity,
        #     "price": order.price,
        #     "stop_loss": order.stop_loss,
        #     "take_profit": order.take_profit,
        #     "time_in_force": order.time_in_force,
        #     "client_order_id": order.id,
        #     "comment": order.comment,
        # }
        #
        # try:
        #     response = self._request("POST", "/orders", json=payload)
        # except Exception as exc:
        #     raise OrderError(str(exc), order=order) from exc
        #
        # return Fill(
        #     order_id=order.id,
        #     broker_order_id=str(response["order_id"]),
        #     status=OrderStatus.FILLED,         # TODO: map from response
        #     symbol=order.symbol,
        #     side=order.side,
        #     filled_qty=response["filled_qty"],
        #     avg_price=response["avg_price"],
        #     message=response.get("message", ""),
        #     raw=response,
        # )

        raise NotImplementedError("TODO: Implement submit() for your broker")

    def cancel(self, broker_order_id: str) -> bool:
        """Cancel an open order by its broker-assigned ID.

        Typical implementation:
          Step 1: Send cancel request to the broker
                  - REST: DELETE /orders/{broker_order_id}
                  - SDK:  client.cancel_order(broker_order_id)

          Step 2: Parse the response to determine success
                  - Return True if the broker confirms cancellation
                  - Return False if the order was already filled/cancelled

          Step 3: Handle errors
                  - Raise OrderError for failures the caller should know about
                  - Raise BrokerError for unexpected API errors

        Args:
            broker_order_id: The broker's own order identifier.

        Returns:
            True if the order was successfully cancelled.
        """
        # try:
        #     response = self._request("DELETE", f"/orders/{broker_order_id}")
        #     return response.get("status") == "cancelled"
        # except Exception as exc:
        #     raise OrderError(str(exc)) from exc

        raise NotImplementedError("TODO: Implement cancel() for your broker")

    def modify(
        self,
        broker_order_id: str,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        quantity: Optional[float] = None,
    ) -> Fill:
        """Modify an existing open order.

        Typical implementation:
          Step 1: Build a payload with only the fields that changed
                  - Only include non-None values

          Step 2: Send the modification request
                  - REST: PATCH /orders/{broker_order_id}
                  - SDK:  client.modify_order(broker_order_id, ...)

          Step 3: Parse the response into a Fill
                  - Return updated Fill with new values

          Step 4: Handle errors
                  - Some brokers require cancel+resubmit instead of modify;
                    implement that logic here if needed

        Args:
            broker_order_id: The broker's order identifier.
            price:    New order price (or None to keep current).
            sl:       New stop-loss price (or None to keep current).
            tp:       New take-profit price (or None to keep current).
            quantity: New quantity (or None to keep current).

        Returns:
            Fill reflecting the modified order state.
        """
        # payload = {}
        # if price is not None:
        #     payload["price"] = price
        # if sl is not None:
        #     payload["stop_loss"] = sl
        # if tp is not None:
        #     payload["take_profit"] = tp
        # if quantity is not None:
        #     payload["qty"] = quantity
        #
        # try:
        #     response = self._request("PATCH", f"/orders/{broker_order_id}", json=payload)
        # except Exception as exc:
        #     raise OrderError(str(exc)) from exc
        #
        # return Fill(
        #     order_id="",
        #     broker_order_id=broker_order_id,
        #     status=OrderStatus.SUBMITTED,    # TODO: map from response
        #     symbol=response["symbol"],
        #     side=Side.BUY,                   # TODO: map from response
        #     filled_qty=0.0,
        #     avg_price=response.get("price", 0.0),
        #     message=response.get("message", ""),
        #     raw=response,
        # )

        raise NotImplementedError("TODO: Implement modify() for your broker")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def positions(self, symbol: Optional[str] = None) -> list[Position]:
        """Return a list of open positions, optionally filtered by symbol.

        Typical implementation:
          Step 1: Fetch open positions from the broker
                  - REST: GET /positions  (or GET /positions?symbol=...)
                  - SDK:  client.get_positions()

          Step 2: Parse each position into a Position dataclass
                  - Map broker's side/direction to Side enum
                  - Extract symbol, quantity, entry_price, unrealized_pnl, ticket

          Step 3: Filter by symbol if provided
                  - Some broker APIs support server-side filtering;
                    otherwise filter the list client-side

          Step 4: Return the list

        Args:
            symbol: Optional symbol to filter by (e.g. "EURUSD").

        Returns:
            List of Position objects.
        """
        # try:
        #     params = {"symbol": symbol} if symbol else {}
        #     response = self._request("GET", "/positions", params=params)
        # except Exception as exc:
        #     raise BrokerError(str(exc)) from exc
        #
        # positions = []
        # for raw_pos in response.get("positions", []):
        #     positions.append(Position(
        #         symbol=raw_pos["symbol"],
        #         side=Side.BUY if raw_pos["side"] == "buy" else Side.SELL,
        #         quantity=raw_pos["qty"],
        #         entry_price=raw_pos["entry_price"],
        #         unrealized_pnl=raw_pos.get("unrealized_pnl", 0.0),
        #         ticket=str(raw_pos["ticket"]),
        #         stop_loss=raw_pos.get("stop_loss"),
        #         take_profit=raw_pos.get("take_profit"),
        #     ))
        # return positions

        raise NotImplementedError("TODO: Implement positions() for your broker")

    def open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Return a list of open/pending orders.

        Typical implementation:
          Step 1: Fetch open orders from the broker
                  - REST: GET /orders?status=open
                  - SDK:  client.get_open_orders()

          Step 2: Optionally filter by symbol

          Step 3: Return as a list of dicts
                  - This method returns raw dicts rather than typed objects
                    because open order shapes vary significantly across brokers

        Args:
            symbol: Optional symbol to filter by.

        Returns:
            List of dicts, each representing an open order.
        """
        # try:
        #     params = {"status": "open"}
        #     if symbol:
        #         params["symbol"] = symbol
        #     response = self._request("GET", "/orders", params=params)
        #     return response.get("orders", [])
        # except Exception as exc:
        #     raise BrokerError(str(exc)) from exc

        raise NotImplementedError("TODO: Implement open_orders() for your broker")

    def account(self) -> Account:
        """Return the current account state.

        Typical implementation:
          Step 1: Fetch account info from the broker
                  - REST: GET /account
                  - SDK:  client.get_account()

          Step 2: Parse the response into an Account dataclass
                  - Map balance, equity, margin_used, margin_free, currency

          Step 3: Return the Account object

        Returns:
            Account with current balances and margin info.
        """
        # try:
        #     response = self._request("GET", "/account")
        # except Exception as exc:
        #     raise BrokerError(str(exc)) from exc
        #
        # return Account(
        #     balance=response["balance"],
        #     equity=response["equity"],
        #     margin_used=response["margin_used"],
        #     margin_free=response["margin_free"],
        #     currency=response.get("currency", "USD"),
        #     account_id=str(response.get("account_id", "")),
        # )

        raise NotImplementedError("TODO: Implement account() for your broker")

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def close_position(self, ticket: str) -> Fill:
        """Close a single open position identified by its ticket/ID.

        Typical implementation:
          Step 1: Send a close request for the given ticket
                  - REST: POST /positions/{ticket}/close
                  - SDK:  client.close_position(ticket)
                  - Some brokers require submitting an opposing order instead;
                    if so, build and submit the opposite-side market order here

          Step 2: Parse the response into a Fill
                  - The Fill should reflect the closing trade's execution

          Step 3: Handle errors
                  - If the position doesn't exist, raise OrderError
                  - For unexpected errors, raise BrokerError

        Args:
            ticket: The broker's position/ticket identifier.

        Returns:
            Fill reflecting the closing execution.
        """
        # try:
        #     response = self._request("POST", f"/positions/{ticket}/close")
        # except Exception as exc:
        #     raise OrderError(f"Failed to close ticket {ticket}: {exc}") from exc
        #
        # return Fill(
        #     order_id="",
        #     broker_order_id=str(response.get("order_id", "")),
        #     status=OrderStatus.FILLED,
        #     symbol=response["symbol"],
        #     side=Side.SELL if response["side"] == "buy" else Side.BUY,
        #     filled_qty=response["qty"],
        #     avg_price=response["close_price"],
        #     message=response.get("message", ""),
        #     raw=response,
        # )

        raise NotImplementedError("TODO: Implement close_position() for your broker")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable name of this broker adapter.

        Return a short string identifying the broker, e.g.:
            "TopstepX"
            "Interactive Brokers"
            "Alpaca"
        """
        # return "MyBroker"

        raise NotImplementedError("TODO: Return your broker's name")

    # ------------------------------------------------------------------
    # Optional: REST API helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        """Send an HTTP request to the broker's REST API.

        This is an OPTIONAL helper for brokers that use REST/HTTP APIs.
        If your broker has a native Python SDK, you can ignore this method
        entirely and call the SDK directly in each method above.

        Typical implementation:
          Step 1: Build the full URL from base_url + path
          Step 2: Send the request using self._session (requests.Session)
          Step 3: Check the HTTP status code
          Step 4: Parse and return the JSON response
          Step 5: Raise BrokerError on HTTP errors or malformed responses

        Args:
            method: HTTP method ("GET", "POST", "PATCH", "DELETE").
            path:   API endpoint path (e.g. "/orders").
            params: Optional query parameters.
            json:   Optional JSON request body.

        Returns:
            Parsed JSON response as a dict.

        Example setup (put this in __init__):
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            })
        """
        # url = f"{self._base_url}{path}"
        #
        # try:
        #     resp = self._session.request(method, url, params=params, json=json, timeout=30)
        #     resp.raise_for_status()
        #     return resp.json()
        # except requests.exceptions.HTTPError as exc:
        #     raise BrokerError(
        #         f"{method} {path} returned {resp.status_code}: {resp.text}",
        #         raw_response=resp.text,
        #     ) from exc
        # except requests.exceptions.ConnectionError as exc:
        #     raise ConnectionError(f"Cannot reach {url}: {exc}") from exc
        # except Exception as exc:
        #     raise BrokerError(f"Unexpected error on {method} {path}: {exc}") from exc

        raise NotImplementedError("TODO: Implement _request() or remove if using an SDK")


# ======================================================================
# SMOKE TEST
# ======================================================================
# Run this file directly after implementing your adapter to verify
# basic connectivity and order flow:
#
#   python -m exec_engine.adapters.my_broker
#
# Or:
#   python exec_engine/adapters/my_broker.py

if __name__ == "__main__":
    from exec_engine import ExecEngine

    # --- Configuration ---
    broker = MyBrokerAdapter(
        api_key="YOUR_API_KEY",           # TODO: fill in
        api_secret="YOUR_API_SECRET",     # TODO: fill in
        base_url="https://api.mybroker.com",  # TODO: fill in
        account_id="YOUR_ACCOUNT_ID",     # TODO: fill in
    )

    engine = ExecEngine(broker)

    # --- 1. Connect ---
    print("[1] Connecting...")
    engine.connect()
    print("    Connected!\n")

    # --- 2. Account info ---
    print("[2] Fetching account info...")
    acct = engine.account()
    print(f"    Balance:  {acct.balance}")
    print(f"    Equity:   {acct.equity}")
    print(f"    Currency: {acct.currency}\n")

    # --- 3. Submit a small test order ---
    # WARNING: This will place a REAL order. Use a demo/paper account!
    print("[3] Submitting test market buy...")
    fill = engine.market_buy("EURUSD", 0.01)  # TODO: use a valid symbol and tiny size
    print(f"    Status:   {fill.status.value}")
    print(f"    Price:    {fill.avg_price}")
    print(f"    BrokerID: {fill.broker_order_id}\n")

    # --- 4. Check positions ---
    print("[4] Fetching positions...")
    positions = engine.positions()
    for pos in positions:
        print(f"    {pos.symbol} {pos.side.value} {pos.quantity} @ {pos.entry_price}")
    if not positions:
        print("    (no open positions)")
    print()

    # --- 5. Close all and disconnect ---
    print("[5] Closing all positions...")
    fills = engine.close_all()
    print(f"    Closed {len(fills)} position(s)\n")

    print("[6] Disconnecting...")
    engine.disconnect()
    print("    Done!")
