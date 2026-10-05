from __future__ import annotations

from olivia.security import REDACTED, contains_secret, make_password_verifier, redact_secrets, verify_password


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


def test_fine_grained_github_pat_is_redacted():
    token = "github_pat_" + ("A" * 24) + "_" + ("b" * 24)
    sample = f"credential={token}"

    assert contains_secret(sample) is True
    redacted = redact_secrets(sample)
    assert token not in redacted
    assert REDACTED in redacted
    assert contains_secret("github_pat_short") is False
