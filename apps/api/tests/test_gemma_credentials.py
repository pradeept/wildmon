import httpx

from scripts.check_gemma_credentials import describe_error


def test_gemma_diagnostic_redacts_key_from_provider_message():
    response = httpx.Response(
        403,
        json={"error": {"status": "PERMISSION_DENIED", "message": "Key secret-key is blocked"}},
    )

    message = describe_error(response, "secret-key")

    assert message == "HTTP 403 PERMISSION_DENIED: Key [REDACTED] is blocked"
    assert "secret-key" not in message
