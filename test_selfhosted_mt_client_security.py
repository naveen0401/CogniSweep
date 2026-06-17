import os

import selfhosted_mt_clients as clients


TRACKED_ENV = [
    "ERRORSWEEP_ENV",
    "APP_ENV",
    "SELF_HOSTED_MT_ALLOW_PRIVATE_ENDPOINTS",
    "SELF_HOSTED_MT_RETRIES",
    "SELF_HOSTED_MT_RETRY_BACKOFF_SECONDS",
]


def with_env(values):
    previous = {key: os.environ.get(key) for key in TRACKED_ENV}
    for key in TRACKED_ENV:
        os.environ.pop(key, None)
    os.environ.update({key: value for key, value in values.items() if value is not None})
    return previous


def restore_env(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text='{"translations":["Hola"]}'):
        self.status_code = status_code
        self.payload = payload if payload is not None else {"translations": ["Hola"]}
        self.text = text

    def json(self):
        return self.payload


def test_production_blocks_local_mt_endpoint_before_network():
    previous = with_env({"ERRORSWEEP_ENV": "production"})
    calls = []
    original_post = clients.requests.post
    clients.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()
    try:
        try:
            clients.translate_with_opus_mt(
                endpoint="http://127.0.0.1:8100/translate",
                api_key="",
                source_language="English",
                target_language="Spanish",
                texts=["Hello"],
            )
        except clients.TranslationRouteError as exc:
            assert "HTTPS" in str(exc) or "private/local" in str(exc)
        else:
            raise AssertionError("production local MT endpoint must be blocked by default")
        assert calls == []
    finally:
        clients.requests.post = original_post
        restore_env(previous)


def test_production_private_mt_endpoint_requires_explicit_override():
    previous = with_env({"ERRORSWEEP_ENV": "production", "SELF_HOSTED_MT_ALLOW_PRIVATE_ENDPOINTS": "true"})
    calls = []
    original_post = clients.requests.post

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    clients.requests.post = fake_post
    try:
        translations, usage = clients.translate_with_opus_mt(
            endpoint="http://127.0.0.1:8100/translate",
            api_key="",
            source_language="English",
            target_language="Spanish",
            texts=["Hello"],
        )
        assert translations == ["Hola"]
        assert usage["success"] is True
        assert len(calls) == 1
    finally:
        clients.requests.post = original_post
        restore_env(previous)


def test_endpoint_credentials_are_rejected_before_network():
    previous = with_env({})
    calls = []
    original_post = clients.requests.post
    clients.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()
    try:
        try:
            clients.translate_with_opus_mt(
                endpoint="https://user:pass@mt.example.com/translate",
                api_key="",
                source_language="English",
                target_language="Spanish",
                texts=["Hello"],
            )
        except clients.TranslationRouteError as exc:
            assert "must not include credentials" in str(exc)
        else:
            raise AssertionError("credential-bearing MT endpoint must be rejected")
        assert calls == []
    finally:
        clients.requests.post = original_post
        restore_env(previous)


def test_transient_mt_endpoint_failures_are_retried():
    previous = with_env({"SELF_HOSTED_MT_RETRIES": "2", "SELF_HOSTED_MT_RETRY_BACKOFF_SECONDS": "0"})
    calls = []
    responses = [
        FakeResponse(status_code=503, payload={"error": "warming"}),
        FakeResponse(status_code=200, payload={"translations": ["Hola"]}),
    ]
    original_post = clients.requests.post

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    clients.requests.post = fake_post
    try:
        translations, usage = clients.translate_with_opus_mt(
            endpoint="https://mt.example.com/translate",
            api_key="",
            source_language="English",
            target_language="Spanish",
            texts=["Hello"],
        )
        assert translations == ["Hola"]
        assert usage["success"] is True
        assert len(calls) == 2
    finally:
        clients.requests.post = original_post
        restore_env(previous)


if __name__ == "__main__":
    test_production_blocks_local_mt_endpoint_before_network()
    test_production_private_mt_endpoint_requires_explicit_override()
    test_endpoint_credentials_are_rejected_before_network()
    test_transient_mt_endpoint_failures_are_retried()
    print("Self-hosted MT client security tests passed.")
