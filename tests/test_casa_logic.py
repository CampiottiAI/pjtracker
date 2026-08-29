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
