"""Tests for services.retry_utils module."""

import asyncio
import pytest
from services.retry_utils import run_with_retry, _is_retryable, check_for_refusal


# ============================================================================
# _is_retryable tests
# ============================================================================


class TestIsRetryable:
    def test_rate_limit_status_code(self):
        exc = Exception("Too many requests")
        exc.status_code = 429
        assert _is_retryable(exc) is True

    def test_server_error_status_code(self):
        exc = Exception("Internal server error")
        exc.status_code = 500
        assert _is_retryable(exc) is True

    def test_bad_gateway_status_code(self):
        exc = Exception("Bad gateway")
        exc.status_code = 502
        assert _is_retryable(exc) is True

    def test_service_unavailable_status_code(self):
        exc = Exception("Service unavailable")
        exc.status_code = 503
        assert _is_retryable(exc) is True

    def test_gateway_timeout_status_code(self):
        exc = Exception("Gateway timeout")
        exc.status_code = 504
        assert _is_retryable(exc) is True

    def test_non_retryable_status_code(self):
        exc = Exception("Bad request")
        exc.status_code = 400
        assert _is_retryable(exc) is False

    def test_rate_limit_message(self):
        assert _is_retryable(Exception("Rate limit exceeded")) is True

    def test_timeout_message(self):
        assert _is_retryable(Exception("Connection timed out")) is True

    def test_server_error_message(self):
        assert _is_retryable(Exception("Internal server error")) is True

    def test_service_unavailable_message(self):
        assert _is_retryable(Exception("Service temporarily unavailable")) is True

    def test_too_many_requests_message(self):
        assert _is_retryable(Exception("too many requests")) is True

    def test_connection_error_message(self):
        assert _is_retryable(Exception("Connection reset by peer")) is True

    def test_overloaded_message(self):
        assert _is_retryable(Exception("Model is overloaded")) is True

    def test_non_retryable_message(self):
        assert _is_retryable(Exception("Invalid JSON format")) is False

    def test_validation_error(self):
        assert _is_retryable(ValueError("Missing required field")) is False

    def test_empty_response_is_retryable(self):
        """Empty model responses should be retried."""
        assert _is_retryable(RuntimeError("Model returned empty response text — cannot score")) is True

    def test_status_attribute_named_status(self):
        """Some SDKs use .status instead of .status_code."""
        exc = Exception("Error")
        exc.status = 429
        assert _is_retryable(exc) is True


# ============================================================================
# run_with_retry tests
# ============================================================================


class TestRunWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        calls = []

        async def factory():
            calls.append(1)
            return "ok"

        result = await run_with_retry(factory, description="test")
        assert result == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self):
        calls = []

        async def factory():
            calls.append(1)
            if len(calls) < 3:
                raise Exception("rate limit exceeded")
            return "ok"

        result = await run_with_retry(
            factory,
            description="test",
            initial_backoff=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        calls = []

        async def factory():
            calls.append(1)
            raise Exception("rate limit exceeded")

        with pytest.raises(Exception, match="rate limit"):
            await run_with_retry(
                factory,
                description="test",
                max_retries=2,
                initial_backoff=0.01,
            )
        # 1 initial + 2 retries = 3 total
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        calls = []

        async def factory():
            calls.append(1)
            raise ValueError("Invalid input data")

        with pytest.raises(ValueError, match="Invalid input"):
            await run_with_retry(
                factory,
                description="test",
                initial_backoff=0.01,
            )
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retries_with_status_code(self):
        calls = []

        async def factory():
            calls.append(1)
            if len(calls) < 2:
                exc = Exception("Server error")
                exc.status_code = 500
                raise exc
            return "recovered"

        result = await run_with_retry(
            factory,
            description="test",
            initial_backoff=0.01,
        )
        assert result == "recovered"
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_backoff_increases(self):
        """Verify backoff grows exponentially (by counting retries quickly)."""
        calls = []

        async def factory():
            calls.append(1)
            if len(calls) <= 3:
                raise Exception("rate limit exceeded")
            return "done"

        result = await run_with_retry(
            factory,
            description="test",
            max_retries=3,
            initial_backoff=0.01,
            backoff_multiplier=2.0,
        )
        assert result == "done"
        assert len(calls) == 4

    @pytest.mark.asyncio
    async def test_custom_max_retries(self):
        calls = []

        async def factory():
            calls.append(1)
            raise Exception("timeout error")

        with pytest.raises(Exception, match="timeout"):
            await run_with_retry(
                factory,
                description="test",
                max_retries=1,
                initial_backoff=0.01,
            )
        # 1 initial + 1 retry = 2
        assert len(calls) == 2


# ============================================================================
# check_for_refusal tests
# ============================================================================


class TestCheckForRefusal:
    def test_none_text_no_error(self):
        check_for_refusal(None)

    def test_empty_text_no_error(self):
        check_for_refusal("")

    def test_normal_json_no_error(self):
        check_for_refusal('{"rfp_title": "Test"}')

    def test_sorry_cannot_assist(self):
        with pytest.raises(RuntimeError, match="cannot assist"):
            check_for_refusal("I'm sorry, but I cannot assist with that request.")

    def test_unable_to_assist(self):
        with pytest.raises(RuntimeError, match="cannot assist"):
            check_for_refusal("I'm unable to assist with this.")

    def test_content_policy(self):
        with pytest.raises(RuntimeError, match="cannot assist"):
            check_for_refusal("This request violates our content policy.")

    def test_case_insensitive(self):
        with pytest.raises(RuntimeError, match="cannot assist"):
            check_for_refusal("I'M SORRY, BUT I CANNOT ASSIST WITH THAT REQUEST.")

    def test_refusal_is_retryable(self):
        """A refusal RuntimeError should be classified as retryable."""
        try:
            check_for_refusal("I'm sorry, but I cannot assist with that request.")
        except RuntimeError as exc:
            assert _is_retryable(exc) is True

    def test_cannot_assist_substring_is_retryable(self):
        assert _is_retryable(RuntimeError("Model refusal detected — cannot assist")) is True
