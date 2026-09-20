"""Pure-Python regression tests for Same As Last qualification."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

SERVICE_DIR = Path(__file__).parents[1] / "plasticos_logistics" / "services"


def _install_odoo_stub() -> None:
    if "odoo.fields" in sys.modules:
        return
    odoo_mod = types.ModuleType("odoo")
    fields_mod = types.ModuleType("odoo.fields")

    class Datetime:
        @staticmethod
        def now():
            return datetime.now(UTC)

    fields_mod.Datetime = Datetime
    odoo_mod.fields = fields_mod
    sys.modules["odoo"] = odoo_mod
    sys.modules["odoo.fields"] = fields_mod


def _load_service(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SERVICE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_install_odoo_stub()
pkg = types.ModuleType("plasticos_logistics_sal_tests")
svc = types.ModuleType("plasticos_logistics_sal_tests.services")
svc.__path__ = [str(SERVICE_DIR)]
sys.modules["plasticos_logistics_sal_tests"] = pkg
sys.modules["plasticos_logistics_sal_tests.services"] = svc
freight_context = _load_service("plasticos_logistics_sal_tests.services.freight_context", "freight_context.py")
sal_resolver = _load_service("plasticos_logistics_sal_tests.services.sal_resolver", "sal_resolver.py")


class _LoadSearch:
    def __init__(self):
        self.last_domain = None
        self.last_kwargs = None
        self.results = []

    def search(self, domain, **kwargs):
        self.last_domain = domain
        self.last_kwargs = kwargs
        return self.results


def _partner(identifier: int, street: str = "100 Origin Way"):
    return SimpleNamespace(
        id=identifier,
        city="Houston",
        country_id=SimpleNamespace(id=233),
        state_id=SimpleNamespace(id=48),
        street=street,
        street2=False,
        zip="77001",
        partner_latitude=29.7604,
        partner_longitude=-95.3698,
        active=True,
        entity_status="active",
    )


def _current_load(searcher: _LoadSearch, *, rate_amount=0.0, carrier=None):
    return SimpleNamespace(
        id=9,
        state="ready_confirmed",
        rate_amount=rate_amount,
        carrier_id=carrier,
        company_id=SimpleNamespace(id=1),
        sale_order_id=None,
        pickup_partner_id=_partner(11),
        delivery_partner_id=_partner(22, "200 Destination Lane"),
        reference_weight=40000.0,
        transaction_id=SimpleNamespace(intake_id=SimpleNamespace(id=73)),
        env={"plasticos.load": searcher},
    )


def test_search_qualifies_intake_without_a_row_cap_or_sql_cutoff():
    searcher = _LoadSearch()
    load = _current_load(searcher)
    decision = sal_resolver.resolve_sal(load)
    assert decision.decision == "miss"
    assert decision.reason == "no_prior_movement"
    assert searcher.last_kwargs.get("limit") is None
    domain = searcher.last_domain
    assert ("transaction_id.intake_id", "=", 73) in domain
    assert not any(term[0] in {"delivered_at", "dispatched_at"} for term in domain if isinstance(term, tuple))


def test_candidate_uses_persisted_fingerprint_not_live_partner_rebuild():
    searcher = _LoadSearch()
    load = _current_load(searcher)
    current = freight_context.build_freight_context(load)
    moved_partner = _partner(11, "999 Moved Facility")
    candidate = SimpleNamespace(
        id=2,
        state="delivered",
        company_id=load.company_id,
        sale_order_id=None,
        transaction_id=SimpleNamespace(intake_id=SimpleNamespace(id=73)),
        pickup_partner_id=moved_partner,
        delivery_partner_id=load.delivery_partner_id,
        freight_context_fingerprint=current.fingerprint,
        delivered_at=datetime.now(UTC) - timedelta(days=2),
        dispatched_at=None,
        carrier_id=_partner(50),
        rate_amount=1850.0,
        rate_currency_id=SimpleNamespace(id=1),
    )
    searcher.results = [candidate]
    decision = sal_resolver.resolve_sal(load)
    assert decision.decision == "hit"
    assert decision.source_load_id == 2


def test_candidate_without_booking_fingerprint_is_not_rebuilt_from_live_address():
    searcher = _LoadSearch()
    load = _current_load(searcher)
    candidate = SimpleNamespace(
        id=3,
        state="delivered",
        company_id=load.company_id,
        sale_order_id=None,
        transaction_id=SimpleNamespace(intake_id=SimpleNamespace(id=73)),
        pickup_partner_id=load.pickup_partner_id,
        delivery_partner_id=load.delivery_partner_id,
        freight_context_fingerprint=False,
        delivered_at=datetime.now(UTC) - timedelta(days=2),
        dispatched_at=None,
        carrier_id=_partner(50),
        rate_amount=1850.0,
        rate_currency_id=SimpleNamespace(id=1),
    )
    searcher.results = [candidate]
    decision = sal_resolver.resolve_sal(load)
    assert decision.decision == "miss"
    assert decision.reason == "no_prior_movement"


def test_expired_matching_movement_keeps_prior_movement_too_old():
    searcher = _LoadSearch()
    load = _current_load(searcher)
    current = freight_context.build_freight_context(load)
    candidate = SimpleNamespace(
        id=4,
        state="delivered",
        company_id=load.company_id,
        sale_order_id=None,
        transaction_id=SimpleNamespace(intake_id=SimpleNamespace(id=73)),
        pickup_partner_id=load.pickup_partner_id,
        delivery_partner_id=load.delivery_partner_id,
        freight_context_fingerprint=current.fingerprint,
        delivered_at=datetime.now(UTC) - timedelta(days=45),
        dispatched_at=None,
        carrier_id=_partner(50),
        rate_amount=1850.0,
        rate_currency_id=SimpleNamespace(id=1),
    )
    searcher.results = [candidate]
    decision = sal_resolver.resolve_sal(load)
    assert decision.decision == "miss"
    assert decision.reason == "prior_movement_too_old"
