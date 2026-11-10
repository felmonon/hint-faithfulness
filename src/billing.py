"""Reconcile an interrupted call only after checking its charge in OpenRouter."""
import argparse
import math
from .common import append_jsonl, utc_now
from .providers import ledger_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--request-key", help="Omit to list pending request IDs and reserved amounts")
    parser.add_argument("--charged-usd", type=float, help="Actual confirmed charge (zero only if confirmed unbilled)")
    args = parser.parse_args()
    spent, pending = ledger_state(args.ledger)
    if args.request_key is None:
        print({"recorded_or_reserved_usd": spent, "pending": pending})
        return
    if args.request_key not in pending:
        parser.error("That request is not pending in this ledger")
    if args.charged_usd is None or not math.isfinite(args.charged_usd) or args.charged_usd < 0:
        parser.error("Provide the confirmed nonnegative --charged-usd amount from your provider account")
    append_jsonl(args.ledger, {"event": "settle", "request_key": args.request_key,
                 "delta_usd": args.charged_usd - pending[args.request_key],
                 "manual_account_reconciliation": True, "at": utc_now()})
    print("Recorded reconciliation. Failed experiment records remain preserved.")


if __name__ == "__main__":
    main()
