"""
Venmo Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Social payment model with stored wallet balance, configurable privacy,
  and multiple funding source types (bank, debit card, credit card).
- Current-user perspective: no registration or account switching.
- Venmo balance is the preferred funding source for outgoing payments.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class VenmoError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        suggested_action: str = "",
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error = {
            "error_code": error_code,
            "message": message,
            "suggested_action": suggested_action,
            "context": context or {},
        }

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Venmo API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 5002,
    "profile": {},
    "contacts": {},
    "transactions": {},
    "requests": {},
    "funding_sources": {},
    "group_payments": {},
    "debit_card": {},
    "debit_card_transactions": [],
}


class VenmoAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Venmo-like social payment platform.

    State variables:
    - profile: {name, username, email, phone, linked_bank_accounts[],
      linked_cards[], balance}
    - contacts: Dict of {contact_id -> {contact_id, name, username, email, phone}}
    - transactions: Dict of {transaction_id -> {transaction_id, type,
      counterparty{contact_id, name, username}, amount, note, status,
      created_at, funding_source, visibility}}
    - requests: Dict of {request_id -> {request_id, direction,
      counterparty{contact_id, name, username}, amount, note, status,
      created_at}}
    - funding_sources: Dict of {source_id -> {source_id, type, name, last4,
      balance, active}}

    Venmo model: wallet balance as primary funding source, configurable
    visibility (public/friends/private), all funding types accepted,
    no daily/monthly transfer limits, bank transfer withdrawal.
    """


    def __init__(self):
        self._id_counters = { "contact": 0, "transaction": 0, "request": 0, "funding_source": 0, "group_payment": 0, }
        self.profile: Dict[str, Any] = {}
        self.contacts: Dict[str, Dict[str, Any]] = {}
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.requests: Dict[str, Dict[str, Any]] = {}
        self.funding_sources: Dict[str, Dict[str, Any]] = {}
        self.group_payments: Dict[str, Dict[str, Any]] = {}
        self.debit_card: Dict[str, Any] = {}
        self.debit_card_transactions: List[Dict[str, Any]] = []
        self._api_description = (
            "This tool belongs to the Venmo social payment API, which provides "
            "peer-to-peer payments with configurable privacy, balance management, "
            "and multiple funding source types."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        """
        Load a scenario from the scenarios folder.
        Args:
            scenario (Dict[str, Any]): The scenario to load
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.contacts = scenario.get("contacts", DEFAULT_STATE_COPY["contacts"])
        self.transactions = scenario.get("transactions", DEFAULT_STATE_COPY["transactions"])
        self.requests = scenario.get("requests", DEFAULT_STATE_COPY["requests"])
        self.funding_sources = scenario.get("funding_sources", DEFAULT_STATE_COPY["funding_sources"])
        self.group_payments = scenario.get("group_payments", DEFAULT_STATE_COPY["group_payments"])
        self.debit_card = scenario.get("debit_card", DEFAULT_STATE_COPY["debit_card"])
        self.debit_card_transactions = scenario.get("debit_card_transactions", DEFAULT_STATE_COPY["debit_card_transactions"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, VenmoAPI):
            return False

        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            model_attr = getattr(self, attr_name)
            ground_truth_attr = getattr(value, attr_name)

            if model_attr != ground_truth_attr:
                return False

        return True

    # -----------------------------------------------------------------------
    # Internal mechanics
    # -----------------------------------------------------------------------

    def _require_contact(self, contact_id: str) -> Dict[str, Any]:
        contact = self.contacts.get(contact_id)
        if not contact:
            raise VenmoError(
                "CONTACT_NOT_FOUND",
                f"Contact '{contact_id}' not found.",
                suggested_action="Use list_contacts() to find valid contact IDs.",
                context={"contact_id": contact_id},
            )
        return contact

    def _require_transaction(self, transaction_id: str) -> Dict[str, Any]:
        txn = self.transactions.get(transaction_id)
        if not txn:
            raise VenmoError(
                "TRANSACTION_NOT_FOUND",
                f"Transaction '{transaction_id}' not found.",
                suggested_action="Use list_transactions() to find valid transaction IDs.",
                context={"transaction_id": transaction_id},
            )
        return txn

    def _require_request(self, request_id: str) -> Dict[str, Any]:
        req = self.requests.get(request_id)
        if not req:
            raise VenmoError(
                "REQUEST_NOT_FOUND",
                f"Request '{request_id}' not found.",
                suggested_action="Use list_requests() to find valid request IDs.",
                context={"request_id": request_id},
            )
        return req

    def _require_funding_source(self, source_id: str) -> Dict[str, Any]:
        src = self.funding_sources.get(source_id)
        if not src:
            raise VenmoError(
                "FUNDING_SOURCE_NOT_FOUND",
                f"Funding source '{source_id}' not found.",
                suggested_action="Use list_funding_sources() to find valid source IDs.",
                context={"source_id": source_id},
            )
        return src

    def _make_counterparty(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "contact_id": contact.get("contact_id", ""),
            "name": contact.get("name", ""),
            "username": contact.get("username", ""),
        }

    def _get_default_funding_source(self) -> Optional[Dict[str, Any]]:
        """Return the first active funding source from linked accounts/cards."""
        for sid in self.profile.get("linked_bank_accounts", []):
            src = self.funding_sources.get(sid)
            if src and src.get("active", True):
                return src
        for sid in self.profile.get("linked_cards", []):
            src = self.funding_sources.get(sid)
            if src and src.get("active", True):
                return src
        return None

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_account_summary(self) -> Dict[str, Any]:
        """
        Get the current user's Venmo profile.

        Returns:
            Dict[str, Any]: Profile with name, username, email, phone,
                linked_bank_accounts, linked_cards, balance.
        """
        return deepcopy(self.profile)

    def get_balance(self) -> Dict[str, Any]:
        """
        Get the current user's Venmo wallet balance.

        Returns:
            Dict[str, Any]:
                balance (float): The current Venmo balance.
        """
        return {"balance": self.profile.get("balance", 0.0)}

    def update_default_visibility(self, visibility: str) -> Dict[str, Any]:
        """
        Set the default privacy level for new transactions.

        Args:
            visibility (str): "public", "friends", or "private".

        Returns:
            Dict[str, Any]:
                default_visibility (str), status (str).
        """
        if visibility not in ("public", "friends", "private"):
            raise VenmoError(
                "INVALID_VISIBILITY",
                f"Invalid visibility '{visibility}'.",
                suggested_action="Use 'public', 'friends', or 'private'.",
                context={"visibility": visibility},
            )
        self.profile["default_visibility"] = visibility
        return {"default_visibility": visibility, "status": "updated"}

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------

    def add_friend(
        self,
        name: str,
        username: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a new contact for quick payments.

        Args:
            name (str): Contact's display name.
            username (str): Contact's Venmo username.
            email (str, optional): Contact's email address.
            phone (str, optional): Contact's phone number.

        Returns:
            Dict[str, Any]: The created contact object.
        """
        contact_id = self._new_id("contact")
        self.contacts[contact_id] = {
            "contact_id": contact_id,
            "name": name,
            "username": username,
            "email": email,
            "phone": phone,
        }
        return deepcopy(self.contacts[contact_id])

    def list_friends(self) -> List[Dict[str, Any]]:
        """
        List all saved contacts.

        Returns:
            List[Dict[str, Any]]: Contact objects.
        """
        return [deepcopy(c) for c in self.contacts.values()]

    def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Get a specific contact by ID.

        Args:
            contact_id (str): The contact's unique identifier.

        Returns:
            Dict[str, Any]: The contact object.
        """
        contact = self._require_contact(contact_id)
        return deepcopy(contact)

    def remove_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Remove a contact from the saved list.

        Args:
            contact_id (str): The contact to remove.

        Returns:
            Dict[str, Any]:
                contact_id (str), status (str).
        """
        self._require_contact(contact_id)
        del self.contacts[contact_id]
        return {"contact_id": contact_id, "status": "removed"}

    # -----------------------------------------------------------------------
    # Sending money
    # -----------------------------------------------------------------------

    def send_money(
        self,
        contact_id: str,
        amount: float,
        note: str,
        funding_source_id: Optional[str] = None,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        """
        Send money to a contact. Venmo balance is used first; if insufficient,
        the specified funding source (or default) is used as fallback.

        Args:
            contact_id (str): The recipient contact.
            amount (float): Amount to send (must be > 0).
            note (str): Transaction note (required for Venmo payments).
            funding_source_id (str, optional): Fallback funding source if
                balance is insufficient. Defaults to first active linked source.
            visibility (str): Privacy setting — "public", "friends", or
                "private". Defaults to "private".

        Returns:
            Dict[str, Any]:
                transaction_id (str), amount (float), status (str), note (str).
        """
        contact = self._require_contact(contact_id)
        if amount <= 0:
            raise VenmoError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )
        if not note:
            raise VenmoError(
                "NOTE_REQUIRED",
                "A note is required for all Venmo transactions.",
                suggested_action="Provide a non-empty note.",
            )
        if visibility not in ("public", "friends", "private"):
            raise VenmoError(
                "INVALID_VISIBILITY",
                f"Invalid visibility '{visibility}'.",
                suggested_action="Use 'public', 'friends', or 'private'.",
                context={"visibility": visibility},
            )

        balance = self.profile.get("balance", 0.0)
        used_source = None

        if balance >= amount:
            # Fully covered by wallet balance
            self.profile["balance"] = balance - amount
        elif balance > 0:
            # Partial from balance, rest from funding source
            remainder = amount - balance
            self.profile["balance"] = 0.0
            src = self._resolve_funding_source(funding_source_id, remainder)
            src["balance"] = src.get("balance", 0) - remainder
            used_source = src["source_id"]
        else:
            # Entirely from funding source
            src = self._resolve_funding_source(funding_source_id, amount)
            src["balance"] = src.get("balance", 0) - amount
            used_source = src["source_id"]

        now = _utc_now_iso()
        txn_id = self._new_id("transaction")
        self.transactions[txn_id] = {
            "transaction_id": txn_id,
            "type": "send",
            "counterparty": self._make_counterparty(contact),
            "amount": amount,
            "note": note,
            "status": "completed",
            "created_at": now,
            "funding_source": used_source,
            "visibility": visibility,
        }

        return {
            "transaction_id": txn_id,
            "amount": amount,
            "status": "completed",
            "note": note,
        }

    def _resolve_funding_source(
        self, source_id: Optional[str], amount: float,
    ) -> Dict[str, Any]:
        """Resolve and validate a funding source for an outgoing payment."""
        if source_id:
            src = self._require_funding_source(source_id)
            if not src.get("active", True):
                raise VenmoError(
                    "SOURCE_INACTIVE",
                    "This funding source is not active.",
                    suggested_action="Activate the source or use a different one.",
                    context={"source_id": source_id},
                )
        else:
            src = self._get_default_funding_source()
            if not src:
                raise VenmoError(
                    "NO_FUNDING_SOURCE",
                    "Insufficient Venmo balance and no linked funding source.",
                    suggested_action="Add a funding source or fund your Venmo balance.",
                )

        src_balance = src.get("balance", 0)
        if src_balance < amount:
            raise VenmoError(
                "INSUFFICIENT_FUNDS",
                "Insufficient funds in the funding source.",
                suggested_action="Use a different funding source or reduce the amount.",
                context={"balance": src_balance, "amount": amount},
            )
        return src

    def cancel_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Cancel a pending transaction. Only pending transactions can be
        cancelled. The amount is refunded to the Venmo balance.

        Args:
            transaction_id (str): The transaction to cancel.

        Returns:
            Dict[str, Any]:
                transaction_id (str), status (str), refunded_amount (float).
        """
        txn = self._require_transaction(transaction_id)
        if txn.get("status") != "pending":
            raise VenmoError(
                "CANNOT_CANCEL",
                f"Cannot cancel a transaction with status '{txn.get('status')}'.",
                suggested_action="Only pending transactions can be cancelled.",
                context={"status": txn.get("status")},
            )

        txn["status"] = "cancelled"
        amount = txn.get("amount", 0)

        # Refund to balance
        self.profile["balance"] = self.profile.get("balance", 0.0) + amount

        return {
            "transaction_id": transaction_id,
            "status": "cancelled",
            "refunded_amount": amount,
        }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get full details of a transaction.

        Args:
            transaction_id (str): The unique transaction identifier.

        Returns:
            Dict[str, Any]: Full transaction object.
        """
        txn = self._require_transaction(transaction_id)
        return deepcopy(txn)

    def list_transactions(
        self,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List transactions, optionally filtered by status.

        Args:
            status (str, optional): Filter by status (completed/pending/
                cancelled/failed). None returns all.
            limit (int): Maximum number of results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Transactions sorted newest first.
        """
        results = []
        for txn in self.transactions.values():
            if status and txn.get("status") != status:
                continue
            results.append(deepcopy(txn))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------------
    # Money requests
    # -----------------------------------------------------------------------

    def request_money(
        self,
        contact_id: str,
        amount: float,
        note: str,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        """
        Request money from a contact.

        Args:
            contact_id (str): The contact to request money from.
            amount (float): Amount to request (must be > 0).
            note (str): Transaction note (required).
            visibility (str): Privacy setting for the request. Defaults
                to "private".

        Returns:
            Dict[str, Any]:
                request_id (str), amount (float), status (str), note (str).
        """
        contact = self._require_contact(contact_id)
        if amount <= 0:
            raise VenmoError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )
        if not note:
            raise VenmoError(
                "NOTE_REQUIRED",
                "A note is required for all Venmo transactions.",
                suggested_action="Provide a non-empty note.",
            )

        now = _utc_now_iso()
        req_id = self._new_id("request")
        self.requests[req_id] = {
            "request_id": req_id,
            "direction": "outgoing",
            "counterparty": self._make_counterparty(contact),
            "amount": amount,
            "note": note,
            "status": "pending",
            "created_at": now,
        }

        return {
            "request_id": req_id,
            "amount": amount,
            "status": "pending",
            "note": note,
        }

    def respond_to_request(
        self,
        request_id: str,
        action: str,
        funding_source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Respond to an incoming money request — either pay or decline.
        Payment uses Venmo balance first, then falls back to the specified
        (or default) funding source.

        Args:
            request_id (str): The request to respond to.
            action (str): "pay" to send the money, or "decline" to reject.
            funding_source_id (str, optional): Funding source to use if
                balance is insufficient. Defaults to first active linked source.

        Returns:
            Dict[str, Any]:
                request_id (str), status (str),
                transaction_id (str | None) — set if action is "pay".
        """
        req = self._require_request(request_id)
        if req.get("direction") != "incoming":
            raise VenmoError(
                "CANNOT_RESPOND",
                "You can only respond to incoming requests.",
                suggested_action="Use cancel_request() for outgoing requests.",
                context={"request_id": request_id, "direction": req.get("direction")},
            )
        if req.get("status") != "pending":
            raise VenmoError(
                "REQUEST_NOT_PENDING",
                f"This request has already been {req.get('status')}.",
                suggested_action="Only pending requests can be responded to.",
                context={"status": req.get("status")},
            )
        if action not in ("pay", "decline"):
            raise VenmoError(
                "INVALID_ACTION",
                f"Invalid action '{action}'. Must be 'pay' or 'decline'.",
                suggested_action="Use 'pay' or 'decline'.",
                context={"action": action},
            )

        if action == "decline":
            req["status"] = "declined"
            return {
                "request_id": request_id,
                "status": "declined",
                "transaction_id": None,
            }

        # Pay the request
        counterparty = req.get("counterparty", {})
        contact_for_txn = {
            "contact_id": counterparty.get("contact_id", ""),
            "name": counterparty.get("name", ""),
            "username": counterparty.get("username", ""),
        }

        amount = req.get("amount", 0)
        balance = self.profile.get("balance", 0.0)
        used_source = None

        if balance >= amount:
            self.profile["balance"] = balance - amount
        elif balance > 0:
            remainder = amount - balance
            self.profile["balance"] = 0.0
            src = self._resolve_funding_source(funding_source_id, remainder)
            src["balance"] = src.get("balance", 0) - remainder
            used_source = src["source_id"]
        else:
            src = self._resolve_funding_source(funding_source_id, amount)
            src["balance"] = src.get("balance", 0) - amount
            used_source = src["source_id"]

        now = _utc_now_iso()
        txn_id = self._new_id("transaction")
        self.transactions[txn_id] = {
            "transaction_id": txn_id,
            "type": "send",
            "counterparty": contact_for_txn,
            "amount": amount,
            "note": req.get("note", ""),
            "status": "completed",
            "created_at": now,
            "funding_source": used_source,
            "visibility": "private",
        }

        req["status"] = "paid"
        return {
            "request_id": request_id,
            "status": "paid",
            "transaction_id": txn_id,
        }

    def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """
        Cancel an outgoing money request that you created.

        Args:
            request_id (str): The request to cancel.

        Returns:
            Dict[str, Any]:
                request_id (str), status (str).
        """
        req = self._require_request(request_id)
        if req.get("direction") != "outgoing":
            raise VenmoError(
                "CANNOT_CANCEL",
                "You can only cancel your own outgoing requests.",
                suggested_action="Use respond_to_request() for incoming requests.",
                context={"request_id": request_id},
            )
        if req.get("status") != "pending":
            raise VenmoError(
                "REQUEST_NOT_PENDING",
                f"This request has already been {req.get('status')}.",
                suggested_action="Only pending requests can be cancelled.",
                context={"status": req.get("status")},
            )
        req["status"] = "cancelled"
        return {"request_id": request_id, "status": "cancelled"}

    def get_request(self, request_id: str) -> Dict[str, Any]:
        """
        Get full details of a money request.

        Args:
            request_id (str): The unique request identifier.

        Returns:
            Dict[str, Any]: Full request object.
        """
        req = self._require_request(request_id)
        return deepcopy(req)

    def list_requests(
        self,
        direction: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List money requests, optionally filtered by direction and status.

        Args:
            direction (str, optional): "outgoing" for requests you sent,
                "incoming" for requests you received. None returns all.
            status (str, optional): Filter by status (pending/paid/declined/
                cancelled). None returns all.

        Returns:
            List[Dict[str, Any]]: Requests sorted newest first.
        """
        results = []
        for req in self.requests.values():
            if direction and req.get("direction") != direction:
                continue
            if status and req.get("status") != status:
                continue
            results.append(deepcopy(req))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Funding sources
    # -----------------------------------------------------------------------

    def add_funding_source(
        self,
        type: str,
        name: str,
        last4: str,
        balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Add a funding source (bank account, debit card, or credit card).

        Args:
            type (str): Type — "bank_account", "debit_card", or "credit_card".
            name (str): Display name (e.g. "Chase Checking").
            last4 (str): Last 4 digits of the account/card number.
            balance (float, optional): Current balance (for bank accounts).

        Returns:
            Dict[str, Any]: The created funding source object.
        """
        if type not in ("bank_account", "debit_card", "credit_card"):
            raise VenmoError(
                "INVALID_SOURCE_TYPE",
                f"Invalid type '{type}'.",
                suggested_action="Use 'bank_account', 'debit_card', or 'credit_card'.",
                context={"type": type},
            )

        source_id = self._new_id("funding_source")
        self.funding_sources[source_id] = {
            "source_id": source_id,
            "type": type,
            "name": name,
            "last4": last4,
            "balance": balance,
            "active": True,
        }

        if type == "bank_account":
            self.profile.setdefault("linked_bank_accounts", []).append(source_id)
        else:
            self.profile.setdefault("linked_cards", []).append(source_id)

        return deepcopy(self.funding_sources[source_id])

    def list_funding_sources(self) -> List[Dict[str, Any]]:
        """
        List all funding sources (bank accounts and cards).

        Returns:
            List[Dict[str, Any]]: Funding source objects.
        """
        return [deepcopy(s) for s in self.funding_sources.values()]

    def activate_funding_source(self, source_id: str) -> Dict[str, Any]:
        """
        Activate a funding source so it can be used for payments.

        Args:
            source_id (str): The funding source to activate.

        Returns:
            Dict[str, Any]:
                source_id (str), active (bool), status (str).
        """
        src = self._require_funding_source(source_id)
        src["active"] = True
        return {"source_id": source_id, "active": True, "status": "activated"}

    def deactivate_funding_source(self, source_id: str) -> Dict[str, Any]:
        """
        Deactivate a funding source so it cannot be used for payments.

        Args:
            source_id (str): The funding source to deactivate.

        Returns:
            Dict[str, Any]:
                source_id (str), active (bool), status (str).
        """
        src = self._require_funding_source(source_id)
        src["active"] = False
        return {"source_id": source_id, "active": False, "status": "deactivated"}

    # -----------------------------------------------------------------------
    # Bank transfers
    # -----------------------------------------------------------------------

    def transfer_to_bank(
        self,
        amount: float,
        source_id: str,
        transfer_type: str = "standard",
    ) -> Dict[str, Any]:
        """
        Transfer Venmo balance to a linked bank account or debit card.
        Standard transfers are free (1-3 business days); instant transfers
        have a 1.75% fee (min $0.25, max $25) and require a debit card or
        bank account.

        Args:
            amount (float): Amount to transfer (must be > 0).
            source_id (str): The bank account or debit card to transfer to.
            transfer_type (str): "standard" (free, 1-3 days) or "instant"
                (1.75% fee, minutes). Defaults to "standard".

        Returns:
            Dict[str, Any]:
                transaction_id (str), amount (float), fee (float),
                transfer_type (str), status (str).
        """
        if amount <= 0:
            raise VenmoError(
                "INVALID_AMOUNT",
                "Amount must be greater than zero.",
                suggested_action="Provide a positive amount.",
                context={"amount": amount},
            )
        if transfer_type not in ("standard", "instant"):
            raise VenmoError(
                "INVALID_TRANSFER_TYPE",
                f"Invalid transfer type '{transfer_type}'.",
                suggested_action="Use 'standard' or 'instant'.",
                context={"transfer_type": transfer_type},
            )

        src = self._require_funding_source(source_id)
        if src.get("type") not in ("bank_account", "debit_card"):
            raise VenmoError(
                "INVALID_TRANSFER_DESTINATION",
                "Transfers can only be sent to bank accounts or debit cards.",
                suggested_action="Use a bank account or debit card.",
                context={"source_id": source_id, "type": src.get("type")},
            )
        if not src.get("active", True):
            raise VenmoError(
                "SOURCE_INACTIVE",
                "This funding source is not active.",
                suggested_action="Activate the source or use a different one.",
                context={"source_id": source_id},
            )

        balance = self.profile.get("balance", 0.0)
        fee = 0.0
        if transfer_type == "instant":
            fee = max(0.25, min(25.0, round(amount * 0.0175, 2)))
        total = amount + fee
        if balance < total:
            raise VenmoError(
                "INSUFFICIENT_BALANCE",
                f"Insufficient Venmo balance. Need ${total:.2f} but have ${balance:.2f}.",
                suggested_action="Reduce the amount or add funds to your balance.",
                context={"balance": balance, "total_needed": total},
            )

        self.profile["balance"] = balance - total
        # Credit the destination account
        if src.get("balance") is not None:
            src["balance"] = src.get("balance", 0) + amount

        now = _utc_now_iso()
        txn_id = self._new_id("transaction")
        self.transactions[txn_id] = {
            "transaction_id": txn_id,
            "type": "transfer",
            "counterparty": {
                "contact_id": None,
                "name": src.get("name", ""),
                "username": "",
            },
            "amount": amount,
            "note": f"Transfer to {src.get('name', 'bank')}",
            "status": "processing",
            "created_at": now,
            "funding_source": source_id,
            "visibility": "private",
        }

        return {
            "transaction_id": txn_id,
            "amount": amount,
            "fee": fee,
            "transfer_type": transfer_type,
            "status": "processing",
        }

    # -----------------------------------------------------------------------
    # Group payments (split bill)
    # -----------------------------------------------------------------------

    def _require_group_payment(self, group_payment_id: str) -> Dict[str, Any]:
        gp = self.group_payments.get(group_payment_id)
        if not gp:
            raise VenmoError(
                "GROUP_PAYMENT_NOT_FOUND",
                f"Group payment '{group_payment_id}' not found.",
                suggested_action="Use get_group_payment() with a valid ID.",
                context={"group_payment_id": group_payment_id},
            )
        return gp

    def create_group_payment(
        self,
        description: str,
        total_amount: float,
        participants: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create a group payment to split a bill among participants. If
        individual amounts are not specified for each participant, the
        total is split evenly. All participant contacts must exist.

        Args:
            description (str): Description of what the payment is for.
            total_amount (float): Total bill amount (must be > 0).
            participants (List[Dict]): Participants to split the bill among. If amounts are omitted, the total is split evenly.
                - contact_id (str): Contact to charge.
                - amount (float): [Optional] Amount to charge this participant.

        Returns:
            Dict[str, Any]:
                group_payment_id (str), description (str),
                total_amount (float), participants (list), status (str).
        """
        if total_amount <= 0:
            raise VenmoError(
                "INVALID_AMOUNT",
                "Total amount must be greater than zero.",
                suggested_action="Provide a positive total amount.",
                context={"total_amount": total_amount},
            )
        if not participants or len(participants) == 0:
            raise VenmoError(
                "NO_PARTICIPANTS",
                "At least one participant is required.",
                suggested_action="Provide a list of participants with contact IDs.",
            )

        # Validate all contacts exist
        for p in participants:
            self._require_contact(p["contact_id"])

        # Determine amounts
        has_amounts = any("amount" in p for p in participants)
        if has_amounts:
            # Validate that amounts sum to total
            specified_sum = sum(p.get("amount", 0) for p in participants)
            if abs(specified_sum - total_amount) > 0.01:
                raise VenmoError(
                    "AMOUNT_MISMATCH",
                    f"Participant amounts ({specified_sum:.2f}) do not sum to total ({total_amount:.2f}).",
                    suggested_action="Ensure participant amounts sum to the total amount.",
                    context={"specified_sum": specified_sum, "total_amount": total_amount},
                )
            resolved = []
            for p in participants:
                contact = self.contacts[p["contact_id"]]
                resolved.append({
                    "contact_id": p["contact_id"],
                    "name": contact.get("name", ""),
                    "amount": p.get("amount", 0),
                    "status": "unpaid",
                })
        else:
            # Split evenly
            per_person = round(total_amount / len(participants), 2)
            resolved = []
            for p in participants:
                contact = self.contacts[p["contact_id"]]
                resolved.append({
                    "contact_id": p["contact_id"],
                    "name": contact.get("name", ""),
                    "amount": per_person,
                    "status": "unpaid",
                })

        now = _utc_now_iso()
        gp_id = self._new_id("group_payment")
        self.group_payments[gp_id] = {
            "group_payment_id": gp_id,
            "description": description,
            "total_amount": total_amount,
            "participants": resolved,
            "status": "active",
            "created_at": now,
        }

        return {
            "group_payment_id": gp_id,
            "description": description,
            "total_amount": total_amount,
            "participants": deepcopy(resolved),
            "status": "active",
        }

    def get_group_payment(
        self, group_payment_id: str,
    ) -> Dict[str, Any]:
        """
        View the status of a group payment including who has paid and
        who has not.

        Args:
            group_payment_id (str): The group payment's unique identifier.

        Returns:
            Dict[str, Any]: Full group payment object with participant
                statuses.
        """
        gp = self._require_group_payment(group_payment_id)
        return deepcopy(gp)

    def remind_group_payment(
        self, group_payment_id: str,
    ) -> Dict[str, Any]:
        """
        Send a reminder to all unpaid participants in a group payment.

        Args:
            group_payment_id (str): The group payment to send reminders for.

        Returns:
            Dict[str, Any]:
                group_payment_id (str), reminded (list of str contact_ids).
        """
        gp = self._require_group_payment(group_payment_id)
        if gp.get("status") != "active":
            raise VenmoError(
                "GROUP_NOT_ACTIVE",
                f"Group payment is '{gp.get('status')}', not active.",
                suggested_action="Only active group payments can be reminded.",
                context={"status": gp.get("status")},
            )

        reminded = []
        for p in gp.get("participants", []):
            if p.get("status") == "unpaid":
                reminded.append(p["contact_id"])

        return {
            "group_payment_id": group_payment_id,
            "reminded": reminded,
        }

    def settle_group_payment(
        self, group_payment_id: str,
    ) -> Dict[str, Any]:
        """
        Mark a group payment as settled.

        Args:
            group_payment_id (str): The group payment to settle.

        Returns:
            Dict[str, Any]:
                group_payment_id (str), status (str).
        """
        gp = self._require_group_payment(group_payment_id)
        if gp.get("status") != "active":
            raise VenmoError(
                "GROUP_NOT_ACTIVE",
                f"Group payment is '{gp.get('status')}', not active.",
                suggested_action="Only active group payments can be settled.",
                context={"status": gp.get("status")},
            )
        gp["status"] = "settled"
        for p in gp.get("participants", []):
            if p.get("status") == "unpaid":
                p["status"] = "settled"
        return {
            "group_payment_id": group_payment_id,
            "status": "settled",
        }

    # -----------------------------------------------------------------------
    # Venmo debit card management
    # -----------------------------------------------------------------------

    def get_debit_card_info(self) -> Dict[str, Any]:
        """
        Get the current user's Venmo debit card details.

        Returns:
            Dict[str, Any]:
                last4 (str), status (str), daily_limit (float),
                current_daily_spent (float), reward_category (str),
                enabled (bool).
        """
        if not self.debit_card:
            raise VenmoError(
                "NO_DEBIT_CARD",
                "No Venmo debit card found on this account.",
                suggested_action="Apply for a Venmo debit card first.",
            )
        return deepcopy(self.debit_card)

    def set_debit_card_spending_limit(
        self, daily_limit: float,
    ) -> Dict[str, Any]:
        """
        Set a daily spending limit on the Venmo debit card.

        Args:
            daily_limit (float): Daily spending limit in dollars.
                Must be between 0 and 3000 (inclusive).

        Returns:
            Dict[str, Any]:
                daily_limit (float), status (str).
        """
        if not self.debit_card:
            raise VenmoError(
                "NO_DEBIT_CARD",
                "No Venmo debit card found on this account.",
                suggested_action="Apply for a Venmo debit card first.",
            )
        if daily_limit < 0 or daily_limit > 3000:
            raise VenmoError(
                "INVALID_LIMIT",
                f"Daily limit must be between 0 and 3000. Got {daily_limit}.",
                suggested_action="Provide a limit between 0 and 3000.",
                context={"daily_limit": daily_limit},
            )
        self.debit_card["daily_limit"] = daily_limit
        return {"daily_limit": daily_limit, "status": "updated"}

    def get_debit_card_transactions(
        self, limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        List recent debit card purchases.

        Args:
            limit (int): Maximum number of results. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Debit card transactions sorted newest
                first.
        """
        if not self.debit_card:
            raise VenmoError(
                "NO_DEBIT_CARD",
                "No Venmo debit card found on this account.",
                suggested_action="Apply for a Venmo debit card first.",
            )
        results = [deepcopy(t) for t in self.debit_card_transactions]
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    def toggle_debit_card(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable the Venmo debit card.

        Args:
            enabled (bool): True to enable, False to disable.

        Returns:
            Dict[str, Any]:
                enabled (bool), status (str).
        """
        if not self.debit_card:
            raise VenmoError(
                "NO_DEBIT_CARD",
                "No Venmo debit card found on this account.",
                suggested_action="Apply for a Venmo debit card first.",
            )
        self.debit_card["enabled"] = enabled
        return {
            "enabled": enabled,
            "status": "enabled" if enabled else "disabled",
        }
