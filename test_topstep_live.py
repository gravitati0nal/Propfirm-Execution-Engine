"""Live integration test for every TopstepAdapter feature.

Connects to the real TopstepX API, exercises every adapter method,
and cleans up after itself. Exits 0 on success, non-zero on failure.
"""

import os
import sys
import time
import traceback

sys.path.insert(0, ".")

from exec_engine import ExecEngine, Order, OrderType, OrderStatus, Side
from exec_engine.adapters.topstep import TopstepAdapter
from exec_engine.exceptions import OrderError

API_KEY = os.environ.get("TOPSTEP_API_KEY", "")
USERNAME = os.environ.get("TOPSTEP_USERNAME", "")

if not API_KEY or not USERNAME:
    print("Set TOPSTEP_API_KEY and TOPSTEP_USERNAME env vars first.")
    sys.exit(1)

SYMBOL = "MNQ"

passed = 0
failed = 0
results = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(("PASS", name, detail))
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1
        results.append(("FAIL", name, detail))
        print(f"  FAIL  {name}" + (f"  ({detail})" if detail else ""))


def main():
    global passed, failed

    # ==================================================================
    # 1. list_accounts (class method, pre-connect)
    # ==================================================================
    print("\n[1] list_accounts")
    accounts = TopstepAdapter.list_accounts(api_key=API_KEY, username=USERNAME)
    check("list_accounts returns a list", isinstance(accounts, list))
    check("list_accounts has at least one account", len(accounts) >= 1)
    first_acct = accounts[0]
    check("account has 'id' key", "id" in first_acct)
    check("account has 'name' key", "name" in first_acct)
    check("account has 'balance' key", "balance" in first_acct)
    check("account has 'canTrade' key", "canTrade" in first_acct)

    tradable = [a for a in accounts if a.get("canTrade")]
    check("at least one tradable account", len(tradable) >= 1)
    account_id = tradable[0]["id"]
    print(f"         Using account id={account_id} name={tradable[0].get('name')}")

    # ==================================================================
    # 2. Constructor + name property
    # ==================================================================
    print("\n[2] constructor + name")
    broker = TopstepAdapter(api_key=API_KEY, username=USERNAME, account_id=account_id)
    check("name property returns 'TopstepX'", broker.name == "TopstepX")
    check("connected is False before connect", broker.connected is False)

    # ==================================================================
    # 3. connect
    # ==================================================================
    print("\n[3] connect")
    engine = ExecEngine(broker)
    engine.connect()
    check("connected is True after connect", broker.connected is True)
    check("account_id is set", broker._account_id == account_id)
    check("JWT token is set", broker._token is not None and len(broker._token) > 10)

    # ==================================================================
    # 4. account
    # ==================================================================
    print("\n[4] account")
    acct = engine.account()
    check("account returns Account", type(acct).__name__ == "Account")
    check("balance is a positive number", acct.balance > 0, f"balance={acct.balance}")
    check("equity equals balance", acct.equity == acct.balance)
    check("margin_used is 0", acct.margin_used == 0.0)
    check("margin_free equals balance", acct.margin_free == acct.balance)
    check("currency is USD", acct.currency == "USD")
    check("account_id matches", acct.account_id == str(account_id))

    # ==================================================================
    # 5. _resolve_symbol (ticker search)
    # ==================================================================
    print("\n[5] _resolve_symbol (search)")
    contract = broker._resolve_symbol(SYMBOL)
    check("resolve returns dict with 'id'", "id" in contract)
    check("contract id starts with CON.", contract["id"].startswith("CON."), contract["id"])
    check("contract has tickSize", "tickSize" in contract)
    check("contract has tickValue", "tickValue" in contract)
    check("contract is activeContract", contract.get("activeContract") is True)
    contract_id = contract["id"]

    # ==================================================================
    # 6. _resolve_symbol (cache hit)
    # ==================================================================
    print("\n[6] _resolve_symbol (cache)")
    contract2 = broker._resolve_symbol(SYMBOL)
    check("cached lookup returns same object", contract2 is contract)

    # ==================================================================
    # 7. _resolve_symbol (full contract ID passthrough)
    # ==================================================================
    print("\n[7] _resolve_symbol (by contract ID)")
    contract3 = broker._resolve_symbol(contract_id)
    check("searchById returns matching id", contract3["id"] == contract_id)

    # ==================================================================
    # 8. positions (baseline -- may or may not be empty)
    # ==================================================================
    print("\n[8] positions (baseline)")
    baseline_positions = engine.positions()
    check("positions returns a list", isinstance(baseline_positions, list))
    print(f"         {len(baseline_positions)} open position(s) at baseline")

    # ==================================================================
    # 9. open_orders (baseline)
    # ==================================================================
    print("\n[9] open_orders (baseline)")
    baseline_orders = engine.open_orders()
    check("open_orders returns a list", isinstance(baseline_orders, list))
    print(f"         {len(baseline_orders)} open order(s) at baseline")

    # ==================================================================
    # 10. submit market buy -> fills immediately
    # ==================================================================
    print("\n[10] submit market buy")
    buy_fill = engine.market_buy(SYMBOL, qty=1)
    check("market buy returns Fill", type(buy_fill).__name__ == "Fill")
    check("broker_order_id is set", buy_fill.broker_order_id != "")
    check("status is FILLED", buy_fill.status == OrderStatus.FILLED, buy_fill.status.value)
    check("filled_qty is 1", buy_fill.filled_qty == 1.0)
    check("avg_price > 0", buy_fill.avg_price > 0, f"price={buy_fill.avg_price}")
    check("side is BUY", buy_fill.side == Side.BUY)

    # ==================================================================
    # 11. positions after buy
    # ==================================================================
    print("\n[11] positions after buy")
    after_buy_positions = engine.positions()
    check("positions list grew or has the MNQ contract",
          len(after_buy_positions) > 0)
    mnq_pos = [p for p in after_buy_positions if p.ticket == contract_id]
    check("MNQ position exists", len(mnq_pos) >= 1)
    if mnq_pos:
        check("position side is BUY", mnq_pos[0].side == Side.BUY)
        check("position entry_price > 0", mnq_pos[0].entry_price > 0)

    # ==================================================================
    # 12. positions filtered by symbol
    # ==================================================================
    print("\n[12] positions filtered by symbol")
    filtered = engine.positions(SYMBOL)
    check("filtered positions returns results", len(filtered) >= 1)
    for p in filtered:
        check(f"filtered pos ticket matches contract", p.ticket == contract_id)

    # ==================================================================
    # 13. close_position (opposing market order)
    # ==================================================================
    print("\n[13] close_position")
    close_fill = engine.close(contract_id)
    check("close returns Fill", type(close_fill).__name__ == "Fill")
    check("close fill broker_order_id set", close_fill.broker_order_id != "")
    check("close fill status is FILLED", close_fill.status == OrderStatus.FILLED, close_fill.status.value)
    check("close fill side is SELL (opposite)", close_fill.side == Side.SELL)

    time.sleep(0.5)
    after_close = engine.positions()
    mnq_after = [p for p in after_close if p.ticket == contract_id]
    check("MNQ position closed (gone or qty reduced)",
          len(mnq_after) == 0 or mnq_after[0].quantity < mnq_pos[0].quantity if mnq_pos else True)

    # ==================================================================
    # 14. submit limit order (far from market, won't fill)
    # ==================================================================
    print("\n[14] submit limit order")
    far_price = round(buy_fill.avg_price * 0.90, 2)
    limit_fill = engine.limit_buy(SYMBOL, qty=1, price=far_price)
    check("limit order returns Fill", type(limit_fill).__name__ == "Fill")
    check("limit order broker_order_id set", limit_fill.broker_order_id != "")
    check("limit order status is SUBMITTED", limit_fill.status == OrderStatus.SUBMITTED, limit_fill.status.value)
    limit_order_id = limit_fill.broker_order_id

    # ==================================================================
    # 15. open_orders shows the limit order
    # ==================================================================
    print("\n[15] open_orders after limit")
    time.sleep(0.3)
    open_after_limit = engine.open_orders()
    ids_open = [str(o.get("id")) for o in open_after_limit]
    check("limit order appears in open_orders", limit_order_id in ids_open, f"looking for {limit_order_id}")

    # ==================================================================
    # 16. open_orders filtered by symbol
    # ==================================================================
    print("\n[16] open_orders filtered")
    filtered_orders = engine.open_orders(SYMBOL)
    ids_filtered = [str(o.get("id")) for o in filtered_orders]
    check("limit order in filtered open_orders", limit_order_id in ids_filtered)

    # ==================================================================
    # 17. modify the limit order
    # ==================================================================
    print("\n[17] modify")
    new_price = round(buy_fill.avg_price * 0.85, 2)
    mod_fill = engine.modify(limit_order_id, price=new_price)
    check("modify returns Fill", type(mod_fill).__name__ == "Fill")
    check("modify status is SUBMITTED", mod_fill.status == OrderStatus.SUBMITTED, mod_fill.status.value)
    check("modify broker_order_id matches", mod_fill.broker_order_id == limit_order_id)

    # ==================================================================
    # 18. cancel the limit order
    # ==================================================================
    print("\n[18] cancel")
    cancel_ok = engine.cancel(limit_order_id)
    check("cancel returns True", cancel_ok is True)

    time.sleep(0.3)
    open_after_cancel = engine.open_orders()
    ids_after_cancel = [str(o.get("id")) for o in open_after_cancel]
    check("cancelled order gone from open_orders", limit_order_id not in ids_after_cancel)

    # ==================================================================
    # 19. close_all (open a position, then close all)
    # ==================================================================
    print("\n[19] close_all")
    sell_fill = engine.market_sell(SYMBOL, qty=1)
    check("market sell fills", sell_fill.status == OrderStatus.FILLED, sell_fill.status.value)

    time.sleep(0.3)
    close_all_fills = engine.close_all()
    check("close_all returns list", isinstance(close_all_fills, list))
    check("close_all closed at least 1", len(close_all_fills) >= 1)
    for f in close_all_fills:
        check(f"close_all fill status FILLED (order {f.broker_order_id})", f.status == OrderStatus.FILLED)

    time.sleep(0.5)
    final_positions = engine.positions()
    check("no positions remaining after close_all", len(final_positions) == 0,
          f"{len(final_positions)} remaining")

    # ==================================================================
    # 20. disconnect
    # ==================================================================
    print("\n[20] disconnect")
    engine.disconnect()
    check("connected is False after disconnect", broker.connected is False)
    check("token cleared", broker._token is None)
    check("contract cache cleared", len(broker._contract_cache) == 0)

    # ==================================================================
    # 21. connect with auto-select (no account_id)
    # ==================================================================
    print("\n[21] connect with auto-select")
    broker2 = TopstepAdapter(api_key=API_KEY, username=USERNAME)
    engine2 = ExecEngine(broker2)
    engine2.connect()
    check("auto-select picked an account", broker2._account_id is not None)
    check("auto-selected account is int", isinstance(broker2._account_id, int))
    engine2.disconnect()
    check("second adapter disconnected", broker2.connected is False)

    return failed == 0


if __name__ == "__main__":
    print("=" * 60)
    print("TopstepX Live Integration Test")
    print("=" * 60)

    success = False
    try:
        success = main()
    except Exception:
        traceback.print_exc()
        failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if not success:
        print("\nSome tests FAILED.")
        sys.exit(1)
    else:
        print("\nAll tests PASSED.")
        sys.exit(0)
