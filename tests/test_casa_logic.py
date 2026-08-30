"""Tests for household bill split logic."""

from __future__ import annotations

import pytest

from pjtracker.casa.bills_logic import compute_split, compute_split_n


def test_compute_split_n_basic_60_40():
    result = compute_split_n([1000.0, 500.0], 2000.0, [0.6, 0.4])
    assert result["total"] == 3500.0
    assert result["nubank_per_person"][0] == 0.6 * 3500 - 1000
    assert result["nubank_per_person"][1] == 0.4 * 3500 - 500
    assert sum(result["nubank_per_person"]) == 2000.0


def test_compute_split_reimbursement():
    result = compute_split_n([2000.0, 0.0], 1000.0, [0.6, 0.4])
    assert result["nubank_per_person"][0] < 0
    assert result["reimbursements"][0] > 0


def test_compute_split_cc_reserved():
    result = compute_split_n(
        [500.0, 300.0],
        2000.0,
        [0.6, 0.4],
        cc_reserved_amount=500.0,
        cc_reserved_person_index=0,
    )
    assert result["cc_reserved_amount"] == 500.0
    assert result["total"] == 2800.0


def test_compute_split_two_person_wrapper():
    result = compute_split(1000.0, 500.0, 2000.0, 0.6)
    assert result["rael_nubank"] + result["fer_nubank"] == 2000.0


def test_pcts_must_sum_to_one():
    with pytest.raises(ValueError, match="pcts must sum"):
        compute_split_n([100.0], 100.0, [0.5])


def test_normalize_cards_from_legacy_nubank():
    from pjtracker.casa.storage import normalize_cards, nubank_from_cards

    cards = normalize_cards(None, 1500.0)
    assert cards == [{"name": "Nubank", "value": 1500.0}]
    assert nubank_from_cards(cards) == 1500.0


def test_normalize_cards_prefers_explicit_list():
    from pjtracker.casa.storage import normalize_cards, nubank_from_cards

    cards = normalize_cards(
        [{"name": "Nubank", "value": 1000.0}, {"name": "Inter", "value": 250.0}],
        9999.0,
    )
    assert len(cards) == 2
    assert nubank_from_cards(cards) == 1250.0


def test_personal_expense_excluded_from_amounts():
    from pjtracker.casa.storage import compute_amounts_from_inputs

    people = [{"id": "rael", "name": "Rael"}, {"id": "fer", "name": "Fer"}]
    expenses = [
        {"description": "Mercado", "amount": 200.0, "paid_by": "rael", "split": True},
        {"description": "Presente", "amount": 80.0, "paid_by": "rael", "split": False},
    ]
    amounts = compute_amounts_from_inputs(people, [], expenses)
    assert amounts == [200.0, 0.0]


def test_legacy_expense_without_split_counts():
    from pjtracker.casa.storage import compute_amounts_from_inputs

    people = [{"id": "rael", "name": "Rael"}, {"id": "fer", "name": "Fer"}]
    expenses = [{"description": "Mercado", "amount": 50.0, "paid_by": "fer"}]
    amounts = compute_amounts_from_inputs(people, [], expenses)
    assert amounts == [0.0, 50.0]


def test_primary_assigned_includes_paid_card_and_personal():
    from pjtracker.casa.storage import primary_assigned_brl

    assigned = primary_assigned_brl(
        ["rael", "fer"],
        [1000.0, 200.0],
        [
            {"description": "Mercado", "amount": 80.0, "paid_by": "rael", "split": False},
            {"description": "Farmácia", "amount": 40.0, "paid_by": "fer", "split": False},
        ],
        [500.0, 300.0],
    )
    assert assigned == 1580.0


def test_primary_assigned_ignores_negative_card():
    from pjtracker.casa.storage import primary_assigned_brl

    assigned = primary_assigned_brl(
        ["rael", "fer"],
        [2000.0, 0.0],
        [],
        [-400.0, 400.0],
    )
    assert assigned == 2000.0

