from __future__ import annotations

from olivia.security import make_password_verifier, verify_password


def test_scrypt_owner_password_verifier_round_trip():
    verifier = make_password_verifier("correct horse battery staple", salt=b"0123456789abcdef")
    assert verifier.startswith("scrypt$")
    assert "correct horse battery staple" not in verifier
    assert verify_password("correct horse battery staple", verifier) is True
    assert verify_password("wrong", verifier) is False


def test_invalid_password_verifier_fails_closed():
    assert verify_password("anything", "") is False
    assert verify_password("anything", "sha256$not-supported") is False
    assert verify_password("anything", "scrypt$broken") is False
