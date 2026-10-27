import pytest
from backend.services.model_client import ModelClient, ModelNotConfiguredError

@pytest.mark.asyncio
async def test_missing_key_fails_before_network_request():
    client = ModelClient(api_key="")
    with pytest.raises(ModelNotConfiguredError):
        await client.chat([{"role": "user", "content": "hello"}])

def test_model_configuration_is_exposed():
    client = ModelClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        reasoning_model="reasoning-test",
        fast_model="fast-test",
    )
    assert client.configured is True
    assert client.reasoning_model == "reasoning-test"
    assert client.fast_model == "fast-test"
    assert client.base_url == "https://example.test/v1/"

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.services.model_client import ModelClientError


def _completion(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.mark.asyncio
async def test_reasoning_failure_retries_with_nano_once():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(side_effect=[TimeoutError("super timed out"), _completion("Nano answer")])
    client._client = sdk

    answer, model = await client.chat_with_model([{"role": "user", "content": "hello"}])

    assert answer == "Nano answer"
    assert model == "nano"
    assert [call.kwargs["model"] for call in sdk.chat.completions.create.await_args_list] == ["super", "nano"]


@pytest.mark.asyncio
async def test_nano_failure_is_reported_after_reasoning_failure():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(side_effect=[TimeoutError("super timed out"), RuntimeError("nano unavailable")])
    client._client = sdk

    with pytest.raises(ModelClientError, match="Both the reasoning model and Nano fallback failed"):
        await client.chat_with_model([{"role": "user", "content": "hello"}])
    assert sdk.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_explicit_nano_call_does_not_retry_nano_again():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(side_effect=RuntimeError("nano unavailable"))
    client._client = sdk

    with pytest.raises(ModelClientError):
        await client.chat_with_model([{"role": "user", "content": "hello"}], model="nano")
    assert sdk.chat.completions.create.await_count == 1

@pytest.mark.asyncio
async def test_streaming_retries_with_nano_if_super_fails_before_first_token():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()

    async def nano_stream():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Nano "))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="stream"))])

    sdk.chat.completions.create = AsyncMock(side_effect=[TimeoutError("super timed out"), nano_stream()])
    client._client = sdk
    chunks = [item async for item in client.stream_chat([{"role": "user", "content": "hello"}])]
    assert chunks == [("Nano ", "nano"), ("stream", "nano")]
    assert [call.kwargs["model"] for call in sdk.chat.completions.create.await_args_list] == ["super", "nano"]

@pytest.mark.asyncio
async def test_non_retryable_reasoning_error_does_not_call_nano():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(side_effect=ValueError("invalid model parameter"))
    client._client = sdk

    with pytest.raises(ModelClientError):
        await client.chat_with_model([{"role": "user", "content": "hello"}])
    assert sdk.chat.completions.create.await_count == 1

@pytest.mark.asyncio
async def test_streaming_does_not_restart_after_partial_output():
    client = ModelClient(api_key="test-key", reasoning_model="super", fast_model="nano")
    sdk = MagicMock()

    async def broken_stream():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"))])
        raise TimeoutError("connection lost mid-stream")

    sdk.chat.completions.create = AsyncMock(return_value=broken_stream())
    client._client = sdk
    chunks = []
    with pytest.raises(ModelClientError, match="partial output"):
        async for chunk in client.stream_chat([{"role": "user", "content": "hello"}]):
            chunks.append(chunk)
    assert chunks == [("partial", "super")]
    assert sdk.chat.completions.create.await_count == 1
