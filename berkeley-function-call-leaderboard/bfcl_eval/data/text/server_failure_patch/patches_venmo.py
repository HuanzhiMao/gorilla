"""Runtime patches for VenmoAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.venmo import VenmoAPI, VenmoError
import uuid

# ─── Source: socrates ───


@VenmoAPI._register_patch("send_money", "unavailable_permanent")
def send_money_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise VenmoError("SERVICE_UNAVAILABLE", "")


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


# ─── Source: srivatsa (alternate-path blockers) ───
# These "blocked" patches close off alternate paths the LLM might take to the
# same end-state, so the must_be_called_functions deterministic check is not
# defeated by a valid-but-different recovery sequence.


@VenmoAPI._register_patch("create_group_payment", "blocked")
def create_group_payment_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


@VenmoAPI._register_patch("request_money", "blocked")
def request_money_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


@VenmoAPI._register_patch("send_money", "blocked")
def send_money_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


# ---------- request_money (cents_integer_schema_permanent) ----------


# ft_extra_42 -- schema_mismatch/permanent. The Venmo request_money API
# has rolled out a v2 schema that requires the amount to be an integer
# cents value (under a new 'amount_cents' field name) rather than the
# legacy float dollars 'amount'. Permanent until the client SDK is
# rebuilt; agent should not keep retrying the same payload.
@VenmoAPI._register_patch("request_money", "cents_integer_schema_permanent")
def request_money_cents_integer_schema_permanent(self, *args, **kwargs):
    """Permanent. Always raises SCHEMA_MIGRATION_REQUIRED naming
    'amount_cents' as the required field. Agent should pivot to
    ZelleAPI.request_transfer or warn the user."""
    raise VenmoError(
        "SCHEMA_MIGRATION_REQUIRED",
        (
            "request_money rejected: the legacy float 'amount' field has "
            "been retired. The v2 schema requires integer cents in "
            "'amount_cents'."
        ),
        (
            "Do NOT retry with the same payload -- the rollout is "
            "permanent. Pivot to an alternate transfer rail (Zelle) or "
            "warn the user the request cannot be sent right now."
        ),
    )


@VenmoAPI._register_patch("add_friend", "blocked")
def add_friend_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


@VenmoAPI._register_patch("get_contact", "blocked")
def get_contact_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


@VenmoAPI._register_patch("list_requests", "blocked")
def list_requests_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")


@VenmoAPI._register_patch("list_transactions", "blocked")
def list_transactions_blocked(self, *args, **kwargs):
    raise VenmoError("FEATURE_DISABLED", "")
