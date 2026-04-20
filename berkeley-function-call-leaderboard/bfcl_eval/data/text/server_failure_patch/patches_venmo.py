"""Runtime patches for VenmoAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.venmo import VenmoAPI, VenmoError
import uuid

# ─── Source: socrates ───


@VenmoAPI._register_patch("send_money", "unavailable_permanent")
def send_money_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise VenmoError(
        "SERVICE_UNAVAILABLE",
        "Venmo payment service is currently unavailable.",
        "Try using Zelle or another payment service.",
    )


@VenmoAPI._register_patch("send_money", "phantom_permanent")
def send_money_phantom_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake transaction without ever sending money.
    The transaction never exists, so get_transaction will correctly fail."""
    amount = kwargs.get("amount", args[1] if len(args) > 1 else 0)
    note = kwargs.get("note", args[2] if len(args) > 2 else "")
    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
        "amount": amount,
        "status": "completed",
        "note": note,
    }


# ─── Source: srivatsa ───


@VenmoAPI._register_patch("create_group_payment", "zero_amounts")
def create_group_payment_zero_amounts(self, *args, **kwargs):
    """
    Calls the original create_group_payment but overwrites all participant
    amounts to $0.00 before returning, simulating a serialization failure
    that drops individual charge amounts while preserving the total_amount field.
    """
    result = self._original_function(*args, **kwargs)
    if isinstance(result, dict) and "participants" in result:
        for participant in result["participants"]:
            participant["amount"] = 0.00
    return result


@VenmoAPI._register_patch("get_transaction", "direction_inversion")
def get_transaction_direction_inversion(self, *args, **kwargs):
    """
    Calls the original get_transaction but flips the transaction type from
    'charge' to 'payment' and inverts the from/to fields, making it appear
    the user sent money to the friend instead of requesting it.
    """
    result = self._original_function(*args, **kwargs)
    if isinstance(result, dict) and result.get("type") == "charge":
        result["type"] = "payment"
        result["status"] = "completed"
        from_user = result.get("to")
        to_user = result.get("from")
        result["from"] = from_user
        result["to"] = to_user
    return result
