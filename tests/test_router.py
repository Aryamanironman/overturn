"""The router must classify the request before any agent runs."""

from __future__ import annotations

from overturn.router import route_request


def test_denial_appeal():
    policy = route_request("Ava's insurer denied her MRI claim. Build an internal appeal.", "denial_appeal")
    assert policy["purpose"] == "denial_appeal"
    assert policy["missing_doc_cap"] == 84


def test_billing_error():
    policy = route_request("This hospital bill has a duplicate charge and an overcharge.", None)
    assert policy["purpose"] == "billing_error"


def test_prior_auth():
    policy = route_request("We need prior authorization for the procedure.", None)
    assert policy["purpose"] == "prior_auth"


def test_default():
    assert route_request("Please look at this claim.", None)["purpose"] == "denial_appeal"
