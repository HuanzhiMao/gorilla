"""Runtime patches for ZelleAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.zelle import ZelleAPI

# ─── Source: srivatsa ───


@ZelleAPI._register_patch("send_transfer", "phantom_send")
def zelle_send_transfer_phantom(self, *args, **kwargs):
    """
    Returns a 200 OK with a valid-looking transaction_id and 'completed' status,
    but never actually persists the transaction. get_transaction on the returned
    txn_id will return TRANSACTION_NOT_FOUND and list_transactions will have no record.
    """
    return {
        "transaction_id": "txn_ls3p",
        "status": "completed",
        "amount": kwargs.get("amount", args[1] if len(args) > 1 else None),
        "recipient": kwargs.get("recipient_identifier", args[0] if args else None)
    }


@ZelleAPI._register_patch("request_transfer", "phantom_request")
def zelle_request_transfer_phantom(self, *args, **kwargs):
    """
    Returns a 200 OK with a valid-looking request_id and 'pending' status,
    but never actually persists the request. list_requests will have no record
    of req_m7k4 in sent or pending requests.
    """
    return {
        "request_id": "req_m7k4",
        "status": "pending",
        "amount": kwargs.get("amount", args[1] if len(args) > 1 else None),
        "payer": kwargs.get("payer_identifier", args[0] if args else None)
    }


@ZelleAPI._register_patch("get_contacts", "stale_contacts")
def zelle_get_recipients_stale(self, *args, **kwargs):
    """
    Returns the contact list but injects a stale last_synced timestamp from
    8 days ago and strips out any contact matching Alex Nguyen, simulating
    a contact index that hasn't picked up recently added users.
    """
    result = self._original_function(*args, **kwargs)
    contacts = [c for c in result.get("contacts", []) if "alex" not in c.get("name", "").lower() and "nguyen" not in c.get("name", "").lower()]
    return {
        "contacts": contacts,
        "metadata": {"last_synced": "2026-02-26T12:00:00Z", "total": len(contacts)}
    }


@ZelleAPI._register_patch("check_recipient_enrolled", "stale_enrollment")
def zelle_check_recipient_enrolled_stale(self, *args, **kwargs):
    """
    Always returns enrolled=false with status UNKNOWN for alex.nguyen@outlook.com,
    simulating a stale enrollment database that hasn't registered the user's
    recent Zelle enrollment.
    """
    identifier = kwargs.get("identifier", args[0] if args else "")
    if "alex.nguyen" in identifier:
        return {"enrolled": False, "status": "UNKNOWN"}
    return self._original_function(*args, **kwargs)


@ZelleAPI._register_patch("get_daily_limit", "stale_cache")
def zelle_get_daily_limit_stale(self, *args, **kwargs):
    """
    Returns a daily limit response that looks healthy ($2,500 remaining)
    but carries a cached_at timestamp from 2 days ago. The real remaining
    limit is only $700 due to a $1,800 transfer made yesterday.
    """
    return {
        "daily_limit": 2500.00,
        "used_today": 0.00,
        "remaining": 2500.00,
        "cached_at": "2026-03-04T10:00:00Z"
    }


@ZelleAPI._register_patch("send_transfer", "limit_exceeded")
def zelle_send_transfer_limit_exceeded(self, *args, **kwargs):
    """
    Always returns DAILY_LIMIT_EXCEEDED revealing the true remaining
    limit is only $700, exposing the stale cache from get_daily_limit.
    """
    return {
        "error_code": "DAILY_LIMIT_EXCEEDED",
        "message": "Transfer exceeds remaining daily limit of $700.00",
        "context": {"actual_remaining": 700.00}
    }


@ZelleAPI._register_patch("get_transfer", "schema_corruption")
def zelle_get_transfer_schema_corruption(self, *args, **kwargs):
    """
    Calls the original get_transaction but overwrites recipient_identifier
    with the sender's own email and nulls out the memo field, simulating
    a backend serialization error that corrupts stored transaction fields.
    """
    result = self._original_function(*args, **kwargs)
    if isinstance(result, dict) and "error_code" not in result:
        sender = getattr(self, "user_email", "user@myemail.com")
        result["recipient_identifier"] = sender
        result["sender_identifier"] = sender
        result["memo"] = None
    return result


@ZelleAPI._register_patch("get_transfer", "decimal_shift")
def zelle_get_transfer_decimal_shift(self, *args, **kwargs):
    """
    Calls the original get_transaction but multiplies the stored amount by 10,
    simulating a decimal-place shift in the transaction ledger. The send_money
    response correctly shows $200, but this returns $2,000 — exposing the
    mismatch the agent must catch.
    """
    result = self._original_function(*args, **kwargs)
    if isinstance(result, dict) and "amount" in result:
        result["amount"] = result["amount"] * 10
    return result


# ─── Source: yash ───


# ft_024 -- decimal shift (amount divided by 10)
@ZelleAPI._register_patch("send_transfer", "decimalshift")
def ft024_send_transfer_decimalshift(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    transaction_id = result["transaction_id"]
    amount = kwargs.get("amount", args[1] if len(args) > 1 else 150.0)
    result["amount"] = round(amount / 10, 2)
    result["status"] = "pending"
    if transaction_id in self.transactions:
        self.transactions[transaction_id]["amount"] = result["amount"]
        self.transactions[transaction_id]["status"] = "pending"
    return result
