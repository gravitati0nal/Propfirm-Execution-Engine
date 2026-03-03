"""Tests for the TopstepAdapter against mocked ProjectX API responses."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from exec_engine.adapters.topstep import TopstepAdapter
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


# ======================================================================
# Helpers
# ======================================================================

def _make_adapter(**kwargs) -> TopstepAdapter:
    defaults = {
        "api_key": "test-key",
        "username": "testuser",
        "account_id": 704,
    }
    defaults.update(kwargs)
    return TopstepAdapter(**defaults)


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ======================================================================
# Authentication / connect
# ======================================================================

class TestConnect:
    @patch.object(TopstepAdapter, "_request")
    @patch.object(TopstepAdapter, "_authenticate")
    def test_connect_with_explicit_account_id(self, mock_auth, mock_req):
        adapter = _make_adapter(account_id=704)
        adapter.connect()
        mock_auth.assert_called_once()
        assert adapter.connected is True
        assert adapter._account_id == 704

    @patch.object(TopstepAdapter, "_request")
    @patch.object(TopstepAdapter, "_authenticate")
    def test_connect_auto_selects_account(self, mock_auth, mock_req):
        mock_req.return_value = {
            "accounts": [
                {"id": 100, "name": "INACTIVE", "canTrade": False},
                {"id": 200, "name": "ACTIVE", "canTrade": True, "balance": 50000},
            ],
            "success": True,
        }
        adapter = _make_adapter(account_id=None)
        adapter.connect()
        assert adapter._account_id == 200

    @patch.object(TopstepAdapter, "_request")
    @patch.object(TopstepAdapter, "_authenticate")
    def test_connect_no_tradable_accounts_raises(self, mock_auth, mock_req):
        mock_req.return_value = {
            "accounts": [{"id": 1, "canTrade": False}],
            "success": True,
        }
        adapter = _make_adapter(account_id=None)
        with pytest.raises(ConnectionError, match="No active tradable accounts"):
            adapter.connect()

    def test_authenticate_success(self):
        adapter = _make_adapter()
        mock_resp = _mock_response({"success": True, "token": "jwt-abc-123"})
        with patch.object(adapter._session, "post", return_value=mock_resp):
            adapter._authenticate()
        assert adapter._token == "jwt-abc-123"
        assert adapter._session.headers["Authorization"] == "Bearer jwt-abc-123"

    def test_authenticate_failure_raises(self):
        adapter = _make_adapter()
        mock_resp = _mock_response({"success": False, "errorMessage": "Invalid key"})
        with patch.object(adapter._session, "post", return_value=mock_resp):
            with pytest.raises(ConnectionError, match="Invalid key"):
                adapter._authenticate()


# ======================================================================
# Disconnect
# ======================================================================

class TestDisconnect:
    @patch.object(TopstepAdapter, "_request")
    @patch.object(TopstepAdapter, "_authenticate")
    def test_disconnect_clears_state(self, mock_auth, mock_req):
        adapter = _make_adapter()
        adapter.connect()
        adapter._contract_cache["NQ"] = {"id": "CON.F.US.ENQ.U25"}
        adapter.disconnect()
        assert adapter.connected is False
        assert adapter._token is None
        assert adapter._contract_cache == {}
        assert "Authorization" not in adapter._session.headers


# ======================================================================
# Contract resolution
# ======================================================================

class TestResolveSymbol:
    @patch.object(TopstepAdapter, "_request")
    def test_resolve_symbol_caches(self, mock_req):
        mock_req.return_value = {
            "contracts": [
                {"id": "CON.F.US.ENQ.U25", "name": "NQU5", "tickSize": 0.25, "tickValue": 5, "activeContract": True, "symbolId": "F.US.ENQ"},
            ],
            "success": True,
        }
        adapter = _make_adapter()
        c1 = adapter._resolve_symbol("NQ")
        c2 = adapter._resolve_symbol("NQ")
        assert c1["id"] == "CON.F.US.ENQ.U25"
        assert c1 is c2
        mock_req.assert_called_once()

    @patch.object(TopstepAdapter, "_request")
    def test_resolve_symbol_no_active_raises(self, mock_req):
        mock_req.return_value = {"contracts": [], "success": True}
        adapter = _make_adapter()
        with pytest.raises(OrderError, match="No active contract"):
            adapter._resolve_symbol("INVALID")

    @patch.object(TopstepAdapter, "_request")
    def test_resolve_full_contract_id(self, mock_req):
        mock_req.return_value = {
            "contract": {"id": "CON.F.US.ENQ.U25", "tickSize": 0.25, "activeContract": True},
            "success": True,
        }
        adapter = _make_adapter()
        c = adapter._resolve_symbol("CON.F.US.ENQ.U25")
        assert c["id"] == "CON.F.US.ENQ.U25"
        mock_req.assert_called_once_with("/api/Contract/searchById", {"contractId": "CON.F.US.ENQ.U25"})


# ======================================================================
# Submit
# ======================================================================

class TestSubmit:
    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_submit_market_order(self, mock_req, mock_resolve):
        mock_resolve.return_value = {"id": "CON.F.US.ENQ.U25", "tickSize": 0.25}
        mock_req.side_effect = [
            {"success": True, "orderId": 9056},
            {"orders": [{"id": 9056, "status": 2, "fillVolume": 1, "filledPrice": 21500.25}], "success": True},
        ]
        adapter = _make_adapter()
        adapter._connected = True
        order = Order(symbol="NQ", side=Side.BUY, order_type=OrderType.MARKET, quantity=1)
        fill = adapter.submit(order)

        assert fill.broker_order_id == "9056"
        assert fill.status == OrderStatus.FILLED
        assert fill.filled_qty == 1.0
        assert fill.avg_price == 21500.25

        place_call = mock_req.call_args_list[0]
        payload = place_call[0][1]
        assert payload["side"] == 0
        assert payload["type"] == 2
        assert payload["size"] == 1
        assert payload["contractId"] == "CON.F.US.ENQ.U25"

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_submit_limit_order(self, mock_req, mock_resolve):
        mock_resolve.return_value = {"id": "CON.F.US.EP.U25", "tickSize": 0.25}
        mock_req.return_value = {"success": True, "orderId": 1234}
        adapter = _make_adapter()
        adapter._connected = True
        order = Order(symbol="ES", side=Side.SELL, order_type=OrderType.LIMIT, quantity=2, price=5500.0)
        fill = adapter.submit(order)

        assert fill.broker_order_id == "1234"
        assert fill.status == OrderStatus.SUBMITTED
        payload = mock_req.call_args[0][1]
        assert payload["side"] == 1
        assert payload["type"] == 1
        assert payload["limitPrice"] == 5500.0
        assert payload["size"] == 2

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_submit_stop_order(self, mock_req, mock_resolve):
        mock_resolve.return_value = {"id": "CON.F.US.RTY.U25", "tickSize": 0.1}
        mock_req.return_value = {"success": True, "orderId": 5555}
        adapter = _make_adapter()
        adapter._connected = True
        order = Order(symbol="RTY", side=Side.BUY, order_type=OrderType.STOP, quantity=3, price=2200.0)
        fill = adapter.submit(order)

        assert fill.broker_order_id == "5555"
        payload = mock_req.call_args[0][1]
        assert payload["type"] == 4
        assert payload["stopPrice"] == 2200.0

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_submit_rejected(self, mock_req, mock_resolve):
        mock_resolve.return_value = {"id": "CON.F.US.ENQ.U25", "tickSize": 0.25}
        mock_req.return_value = {"success": False, "errorMessage": "Insufficient funds"}
        adapter = _make_adapter()
        adapter._connected = True
        order = Order(symbol="NQ", side=Side.BUY, order_type=OrderType.MARKET, quantity=1)
        fill = adapter.submit(order)

        assert fill.status == OrderStatus.REJECTED
        assert fill.message == "Insufficient funds"
        assert fill.filled_qty == 0.0

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_submit_casts_quantity_to_int(self, mock_req, mock_resolve):
        mock_resolve.return_value = {"id": "CON.F.US.ENQ.U25", "tickSize": 0.25}
        mock_req.return_value = {"success": True, "orderId": 100}
        adapter = _make_adapter()
        adapter._connected = True
        order = Order(symbol="NQ", side=Side.BUY, order_type=OrderType.LIMIT, quantity=2.7, price=21000.0)
        adapter.submit(order)
        payload = mock_req.call_args[0][1]
        assert payload["size"] == 2
        assert isinstance(payload["size"], int)


# ======================================================================
# Cancel
# ======================================================================

class TestCancel:
    @patch.object(TopstepAdapter, "_request")
    def test_cancel_success(self, mock_req):
        mock_req.return_value = {"success": True}
        adapter = _make_adapter()
        assert adapter.cancel("26974") is True
        payload = mock_req.call_args[0][1]
        assert payload["orderId"] == 26974
        assert payload["accountId"] == 704

    @patch.object(TopstepAdapter, "_request")
    def test_cancel_failure(self, mock_req):
        mock_req.return_value = {"success": False, "errorMessage": "Order not found"}
        adapter = _make_adapter()
        assert adapter.cancel("99999") is False


# ======================================================================
# Modify
# ======================================================================

class TestModify:
    @patch.object(TopstepAdapter, "_request")
    def test_modify_price(self, mock_req):
        mock_req.return_value = {"success": True}
        adapter = _make_adapter()
        fill = adapter.modify("26974", price=5200.0)
        assert fill.status == OrderStatus.SUBMITTED
        payload = mock_req.call_args[0][1]
        assert payload["limitPrice"] == 5200.0
        assert payload["orderId"] == 26974

    @patch.object(TopstepAdapter, "_request")
    def test_modify_rejected(self, mock_req):
        mock_req.return_value = {"success": False, "errorMessage": "Cannot modify"}
        adapter = _make_adapter()
        fill = adapter.modify("123", price=100.0)
        assert fill.status == OrderStatus.REJECTED
        assert fill.message == "Cannot modify"

    @patch.object(TopstepAdapter, "_request")
    def test_modify_quantity_cast_to_int(self, mock_req):
        mock_req.return_value = {"success": True}
        adapter = _make_adapter()
        adapter.modify("100", quantity=3.5)
        payload = mock_req.call_args[0][1]
        assert payload["size"] == 3
        assert isinstance(payload["size"], int)


# ======================================================================
# Positions
# ======================================================================

class TestPositions:
    @patch.object(TopstepAdapter, "_request")
    def test_positions_returns_mapped_list(self, mock_req):
        mock_req.return_value = {
            "positions": [
                {"id": 6124, "accountId": 704, "contractId": "CON.F.US.ENQ.U25", "type": 1, "size": 2, "averagePrice": 21500.0},
                {"id": 6125, "accountId": 704, "contractId": "CON.F.US.EP.U25", "type": 2, "size": 1, "averagePrice": 5500.0},
            ],
            "success": True,
        }
        adapter = _make_adapter()
        positions = adapter.positions()
        assert len(positions) == 2
        assert positions[0].side == Side.BUY
        assert positions[0].quantity == 2.0
        assert positions[0].entry_price == 21500.0
        assert positions[0].ticket == "CON.F.US.ENQ.U25"
        assert positions[1].side == Side.SELL

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_positions_filtered_by_symbol(self, mock_req, mock_resolve):
        mock_req.return_value = {
            "positions": [
                {"id": 1, "contractId": "CON.F.US.ENQ.U25", "type": 1, "size": 1, "averagePrice": 21000.0},
                {"id": 2, "contractId": "CON.F.US.EP.U25", "type": 2, "size": 1, "averagePrice": 5000.0},
            ],
            "success": True,
        }
        mock_resolve.return_value = {"id": "CON.F.US.ENQ.U25"}
        adapter = _make_adapter()
        positions = adapter.positions("NQ")
        assert len(positions) == 1
        assert positions[0].ticket == "CON.F.US.ENQ.U25"


# ======================================================================
# Open orders
# ======================================================================

class TestOpenOrders:
    @patch.object(TopstepAdapter, "_request")
    def test_open_orders_returns_raw_dicts(self, mock_req):
        mock_req.return_value = {
            "orders": [{"id": 26970, "contractId": "CON.F.US.EP.U25", "status": 1}],
            "success": True,
        }
        adapter = _make_adapter()
        orders = adapter.open_orders()
        assert len(orders) == 1
        assert orders[0]["id"] == 26970

    @patch.object(TopstepAdapter, "_resolve_symbol")
    @patch.object(TopstepAdapter, "_request")
    def test_open_orders_filtered_by_symbol(self, mock_req, mock_resolve):
        mock_req.return_value = {
            "orders": [
                {"id": 1, "contractId": "CON.F.US.ENQ.U25"},
                {"id": 2, "contractId": "CON.F.US.EP.U25"},
            ],
            "success": True,
        }
        mock_resolve.return_value = {"id": "CON.F.US.EP.U25"}
        adapter = _make_adapter()
        orders = adapter.open_orders("ES")
        assert len(orders) == 1
        assert orders[0]["contractId"] == "CON.F.US.EP.U25"


# ======================================================================
# Account
# ======================================================================

class TestAccount:
    @patch.object(TopstepAdapter, "_request")
    def test_account_returns_mapped_account(self, mock_req):
        mock_req.return_value = {
            "accounts": [{"id": 704, "name": "TEST", "balance": 50000, "canTrade": True}],
            "success": True,
        }
        adapter = _make_adapter()
        acct = adapter.account()
        assert isinstance(acct, Account)
        assert acct.balance == 50000.0
        assert acct.equity == 50000.0
        assert acct.margin_used == 0.0
        assert acct.margin_free == 50000.0
        assert acct.account_id == "704"

    @patch.object(TopstepAdapter, "_request")
    def test_account_not_found_raises(self, mock_req):
        mock_req.return_value = {"accounts": [{"id": 999, "balance": 0}], "success": True}
        adapter = _make_adapter()
        with pytest.raises(BrokerError, match="Account 704 not found"):
            adapter.account()


# ======================================================================
# Close position
# ======================================================================

class TestClosePosition:
    @patch.object(TopstepAdapter, "submit")
    @patch.object(TopstepAdapter, "positions")
    def test_close_position_submits_opposite_market(self, mock_positions, mock_submit):
        mock_positions.return_value = [
            Position(symbol="CON.F.US.ENQ.U25", side=Side.BUY, quantity=2, entry_price=21500.0, ticket="CON.F.US.ENQ.U25"),
        ]
        mock_submit.return_value = Fill(
            order_id="x", broker_order_id="9999", status=OrderStatus.FILLED,
            symbol="CON.F.US.ENQ.U25", side=Side.SELL, filled_qty=2, avg_price=21600.0,
        )
        adapter = _make_adapter()
        fill = adapter.close_position("CON.F.US.ENQ.U25")
        assert fill.status == OrderStatus.FILLED
        submitted_order: Order = mock_submit.call_args[0][0]
        assert submitted_order.side == Side.SELL
        assert submitted_order.order_type == OrderType.MARKET
        assert submitted_order.quantity == 2

    @patch.object(TopstepAdapter, "positions")
    def test_close_position_not_found_raises(self, mock_positions):
        mock_positions.return_value = []
        adapter = _make_adapter()
        with pytest.raises(OrderError, match="No open position"):
            adapter.close_position("CON.NONEXISTENT")


# ======================================================================
# Close all
# ======================================================================

class TestCloseAll:
    @patch.object(TopstepAdapter, "close_position")
    @patch.object(TopstepAdapter, "positions")
    def test_close_all_iterates_positions(self, mock_positions, mock_close):
        mock_positions.return_value = [
            Position(symbol="CON.F.US.ENQ.U25", side=Side.BUY, quantity=1, entry_price=21500.0, ticket="CON.F.US.ENQ.U25"),
            Position(symbol="CON.F.US.EP.U25", side=Side.SELL, quantity=2, entry_price=5500.0, ticket="CON.F.US.EP.U25"),
        ]
        mock_close.return_value = Fill(
            order_id="", broker_order_id="X", status=OrderStatus.FILLED,
            symbol="", side=Side.BUY, filled_qty=1, avg_price=0,
        )
        adapter = _make_adapter()
        fills = adapter.close_all()
        assert len(fills) == 2
        assert mock_close.call_count == 2


# ======================================================================
# Token refresh on 401
# ======================================================================

class TestTokenRefresh:
    def test_request_retries_on_401(self):
        adapter = _make_adapter()
        adapter._token = "expired-token"
        adapter._session.headers["Authorization"] = "Bearer expired-token"

        first_resp = _mock_response({}, status_code=401)
        second_resp = _mock_response({"success": True, "data": "ok"})
        auth_resp = _mock_response({"success": True, "token": "new-token"})

        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            url = args[0] if args else kwargs.get("url", "")
            if "loginKey" in str(url):
                return auth_resp
            if call_count["n"] <= 1:
                return first_resp
            return second_resp

        with patch.object(adapter._session, "post", side_effect=side_effect):
            result = adapter._request("/api/test", {})

        assert result == {"success": True, "data": "ok"}
        assert adapter._token == "new-token"


# ======================================================================
# list_accounts (class method)
# ======================================================================

class TestListAccounts:
    def test_list_accounts_returns_all(self):
        auth_resp = _mock_response({"success": True, "token": "tok"})
        acct_resp = _mock_response({
            "success": True,
            "accounts": [
                {"id": 100, "name": "Acct A", "balance": 50000, "canTrade": True, "isVisible": True},
                {"id": 200, "name": "Acct B", "balance": 75000, "canTrade": True, "isVisible": True},
                {"id": 300, "name": "Acct C", "balance": 0, "canTrade": False, "isVisible": False},
            ],
        })

        with patch("requests.Session") as MockSession:
            session_inst = MagicMock()
            session_inst.headers = {}
            session_inst.post.side_effect = [auth_resp, acct_resp]
            MockSession.return_value = session_inst

            accounts = TopstepAdapter.list_accounts(api_key="key123", username="user")

        assert len(accounts) == 3
        assert accounts[0]["id"] == 100
        assert accounts[1]["name"] == "Acct B"
        assert accounts[2]["canTrade"] is False

    def test_list_accounts_auth_failure_raises(self):
        auth_resp = _mock_response({"success": False, "errorMessage": "Bad key"})

        with patch("requests.Session") as MockSession:
            session_inst = MagicMock()
            session_inst.headers = {}
            session_inst.post.return_value = auth_resp
            MockSession.return_value = session_inst

            with pytest.raises(ConnectionError, match="Bad key"):
                TopstepAdapter.list_accounts(api_key="invalid", username="user")

    def test_list_accounts_empty(self):
        auth_resp = _mock_response({"success": True, "token": "tok"})
        acct_resp = _mock_response({"success": True, "accounts": []})

        with patch("requests.Session") as MockSession:
            session_inst = MagicMock()
            session_inst.headers = {}
            session_inst.post.side_effect = [auth_resp, acct_resp]
            MockSession.return_value = session_inst

            accounts = TopstepAdapter.list_accounts(api_key="key123", username="user")

        assert accounts == []


# ======================================================================
# Identity
# ======================================================================

class TestIdentity:
    def test_name(self):
        adapter = _make_adapter()
        assert adapter.name == "TopstepX"
