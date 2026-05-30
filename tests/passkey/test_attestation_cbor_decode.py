"""
Regression smoke for the WebAuthn attestation CBOR-decode path on cbor2 6.x.

Background: stress-test F5 tried to cap ``cbor2<6`` (via a ``[tool.uv]``
constraint that never actually applied under pip), out of concern that the
6.x major changed the CBOR API the passkey *attestation* path relies on.
Production has in fact run cbor2 6.x the whole time. This test pins the concern
to ground truth: it builds a valid ``attestationObject`` (COSE EC2 P-256 key →
``authData`` → CBOR) and drives it through ``py_webauthn``'s real parse path —
``parse_attestation_object`` (``cbor2.loads``) and
``decode_credential_public_key`` (COSE/CBOR) — asserting both decode cleanly.
If a future cbor2 bump breaks py_webauthn's decode, this fails loudly instead of
only surfacing during a live passkey registration.

``registration`` (``generate_registration_options``) is also smoked to cover the
``encode_cbor`` direction.
"""

import os
import struct

import cbor2
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn import generate_registration_options, options_to_json
from webauthn.helpers import (
    decode_credential_public_key,
    parse_attestation_object,
)
from webauthn.helpers.structs import COSEAlgorithmIdentifier


def _cose_ec2_p256_key() -> bytes:
    """Build a COSE_Key (CBOR) for a freshly generated EC2 P-256 public key."""
    public_numbers = (
        ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    )
    return cbor2.dumps(
        {
            1: 2,  # kty: EC2
            3: -7,  # alg: ES256
            -1: 1,  # crv: P-256
            -2: public_numbers.x.to_bytes(32, "big"),  # x
            -3: public_numbers.y.to_bytes(32, "big"),  # y
        }
    )


def _attestation_object() -> bytes:
    """Build a minimal but structurally valid ``none``-fmt attestationObject."""
    cose_key = _cose_ec2_p256_key()
    rp_id_hash = os.urandom(32)
    flags = bytes([0b01000101])  # UP + UV + AT (attested credential data present)
    sign_count = struct.pack(">I", 1)
    aaguid = b"\x00" * 16
    cred_id = os.urandom(16)
    auth_data = (
        rp_id_hash
        + flags
        + sign_count
        + aaguid
        + struct.pack(">H", len(cred_id))
        + cred_id
        + cose_key
    )
    return cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})


def test_attestation_object_cbor_decodes_on_cbor2_6x():
    """py_webauthn parses an attestationObject + COSE key cleanly on cbor2 6.x."""
    parsed = parse_attestation_object(_attestation_object())

    assert parsed.fmt == "none"
    attested = parsed.auth_data.attested_credential_data
    assert attested is not None

    public_key = decode_credential_public_key(attested.credential_public_key)
    # ES256 / EC2 P-256 round-tripped through cbor2 without API breakage.
    assert public_key.alg == COSEAlgorithmIdentifier.ECDSA_SHA_256


def test_registration_options_encode_cbor_path():
    """generate_registration_options + options_to_json exercise the encode path."""
    options = generate_registration_options(
        rp_id="scalemate.me",
        rp_name="ScaleMate",
        user_name="passkey-smoke@example.test",
    )
    # options_to_json exercises the serialization the register ceremony depends on.
    assert len(options_to_json(options)) > 0
