"""Runtime patches for VanguardAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.vanguard import (
    VanguardAPI,
    VanguardError,
)
import uuid

# ============================================================================
# Patches below, grouped by method, with scenario ID comments
# ============================================================================

# ---------- setup_auto_invest ----------


# ft_extra_20 -- Vanguard auto-invest returns fake investment_id but never
# persists the schedule. list_auto_investments will not show it.
@VanguardAPI._register_patch("setup_auto_invest", "autoinvest_noop_permanent")
def setup_auto_invest_autoinvest_noop_permanent(self, fund_id, amount, frequency, *args, **kwargs):
    """Permanent silent no-op. Returns a fake success payload but never writes
    the auto_investments record, so any subsequent list/cancel cannot find it."""
    from datetime import datetime, timezone, timedelta
    freq_days = {"weekly": 7, "biweekly": 14, "monthly": 30, "quarterly": 90}
    next_exec = (
        datetime.now(timezone.utc) + timedelta(days=freq_days.get(frequency, 30))
    ).isoformat()
    return {
        "investment_id": f"auto_invest_{uuid.uuid4().hex[:8]}",
        "fund_id": fund_id,
        "amount": amount,
        "frequency": frequency,
        "next_execution": next_exec,
        "status": "active",
    }


# ---------- get_rmd_status ----------


# ft_extra_21 -- RMD status returns a last_calculated_rmd snapshot that was
# computed before the 2026 IRS life-expectancy table update. Permanent until
# the platform recomputes; agent must treat the figure as stale.
@VanguardAPI._register_patch("get_rmd_status", "stale_rmd_pretable_update_permanent")
def get_rmd_status_stale_rmd_pretable_update_permanent(self, *args, **kwargs):
    """Permanent. Returns a stale RMD figure tagged with a pre-2026 calculation
    timestamp. The underlying rmd_info may be unset; return a canonical stale
    snapshot so the scenario is deterministic."""
    return {
        "birth_date": self.rmd_info.get("birth_date") or "1952-07-14",
        "last_calculated_rmd": 14820.00,
        "last_calculated_at": "2025-11-30T00:00:00Z",
        "withdrawal_schedule": self.rmd_info.get("withdrawal_schedule"),
        "cache_status": "stale",
        "calculation_basis": "irs_life_expectancy_table_2022",
    }


# ---------- execute_rebalance ----------


# ft_extra_22 -- execute_rebalance rejects standard call with a
# schema-strict error complaining about a missing 'acknowledgement_token'
# undocumented hint parameter. Temporary: only the first call fails;
# subsequent calls succeed because the token cache warms up.
@VanguardAPI._register_patch("execute_rebalance", "schema_strict_ack_token_temporary")
def execute_rebalance_schema_strict_ack_token_temporary(self, *args, **kwargs):
    """Temporary. First call raises MISSING_REQUIRED_FIELD naming an
    undocumented 'acknowledgement_token' parameter; second call and beyond
    fall through to the original implementation. This mimics a staging-side
    schema drift that self-heals once the client-side cache reloads."""
    if self._patch_call_count <= 1:
        raise VanguardError(
            error_code="MISSING_REQUIRED_FIELD",
            message=(
                "Request validation failed: field 'acknowledgement_token' is "
                "required for rebalance execution in the new compliance schema."
            ),
            suggested_action=(
                "Confirm the rebalance plan with the user, then retry without "
                "the token -- the server will synthesize one on the second "
                "attempt during the rollout window."
            ),
            context={"schema_version": "rebalance_v2"},
        )
    return self._original_function(*args, **kwargs)


# ---------- cancel_auto_invest ----------


# ft_extra_80 -- cancel_auto_invest returns a fake "canceled" status for the
# requested investment_id but never flips the underlying record's status.
# A subsequent list_auto_investments will still surface the schedule as
# active.  Permanent silent no-op.
@VanguardAPI._register_patch("cancel_auto_invest", "cancel_noop_permanent")
def cancel_auto_invest_cancel_noop_permanent(self, investment_id, *args, **kwargs):
    """Permanent silent no-op. Reports the cancellation but the record in
    self.auto_investments is left active. Recovery: re-read with
    list_auto_investments and notice the schedule is still there."""
    return {"investment_id": investment_id, "status": "canceled"}


# ---------- contribute ----------


# ft_extra_81 -- contribute returns a fresh contribution_id and a "completed"
# status but the underlying contributions dict is never written. Cash
# balance / buying_power is also not credited. Permanent silent no-op.
@VanguardAPI._register_patch("contribute", "contribution_noop_permanent")
def contribute_contribution_noop_permanent(self, amount, *args, **kwargs):
    """Permanent silent no-op. Echoes a contribution receipt without
    persisting the contribution row or updating buying_power/cash_balance.
    Recovery: re-read profile cash_balance and notice the contribution did
    not land."""
    from datetime import datetime, timezone
    tax_year = kwargs.get("tax_year")
    if tax_year is None and len(args) >= 1:
        tax_year = args[0]
    if tax_year is None:
        tax_year = datetime.now(timezone.utc).year
    return {
        "contribution_id": f"contribution_{uuid.uuid4().hex[:8]}",
        "amount": amount,
        "tax_year": tax_year,
        "status": "completed",
    }


# ---------- get_rebalance_preview ----------


# ft_extra_82 -- get_rebalance_preview pulls from a snapshot taken before
# the recent equity run-up, so the suggested_trades vector reflects a
# stale "no rebalance needed" picture even though current_allocation has
# drifted well beyond tolerance. Permanent: cache rebuild is upstream.
@VanguardAPI._register_patch("get_rebalance_preview", "pre_rally_stale_permanent")
def get_rebalance_preview_pre_rally_stale_permanent(self, *args, **kwargs):
    """Permanent data_staleness. Returns a rebalance preview that uses a
    stale current_allocation snapshot (60/30/10 -- exactly on target),
    suggesting no trades are needed even when the live portfolio is far
    from target. Recovery: cross-check against get_holdings and the
    user's actual holdings to spot the discrepancy."""
    target = self.target_allocation or {
        "stocks_percent": 60, "bonds_percent": 30, "cash_percent": 10,
    }
    return {
        "current_allocation": {
            "stocks_percent": float(target.get("stocks_percent", 60)),
            "bonds_percent": float(target.get("bonds_percent", 30)),
            "cash_percent": float(target.get("cash_percent", 10)),
        },
        "target_allocation": {
            "stocks_percent": float(target.get("stocks_percent", 60)),
            "bonds_percent": float(target.get("bonds_percent", 30)),
            "cash_percent": float(target.get("cash_percent", 10)),
        },
        "suggested_trades": [],
        "drift_score": 0.0,
        "snapshot_taken_at": "2026-01-15T00:00:00Z",
        "cache_status": "stale",
    }


# ---------- list_auto_investments ----------


# ft_extra_83 -- list_auto_investments first call returns an empty list
# (a stale-index regression at the platform). Second call falls through
# and returns the real active schedules. Recovery: retry once.
@VanguardAPI._register_patch("list_auto_investments", "stale_index_temporary")
def list_auto_investments_stale_index_temporary(self, *args, **kwargs):
    """Temporary data_staleness. First invocation returns []; second and
    later invocations fall through to the real implementation."""
    if self._patch_call_count <= 1:
        return []
    return self._original_function(*args, **kwargs)
