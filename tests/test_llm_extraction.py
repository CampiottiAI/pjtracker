"""Exercise the actual SDK request/response path without contacting Maritaca."""

import json

import httpx
import pytest
from openai import OpenAI

from pjtracker import llm_extraction as llm


def response_json(data):
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": "completed",
        "model": "s5",
        "output": [
            {"id": "rs_test", "type": "reasoning", "summary": []},
            {
                "id": "msg_test",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": json.dumps(data), "annotations": []}
                ],
            },
        ],
    }


@pytest.fixture
def mock_maritaca(monkeypatch):
    requests = []
    replies = []

    def handle(request):
        requests.append(request)
        return replies.pop(0)

    monkeypatch.setenv("MARITACA_TIMEOUT_SECONDS", "720")
    monkeypatch.setattr(llm, "DEFAULT_MODEL", "s5")
    monkeypatch.setattr(llm, "DEFAULT_SERVICE_TIER", "flex")
    monkeypatch.setattr(llm, "_read_api_key", lambda: "fake-test-key")
    real_openai = OpenAI
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        def create_client(**kwargs):
            return real_openai(**kwargs, http_client=transport)

        monkeypatch.setattr(llm, "OpenAI", create_client)
        llm._get_client.cache_clear()
        try:
            yield requests, replies
        finally:
            llm._get_client().close()
            llm._get_client.cache_clear()


def test_s5_flex_preserves_file_schema_and_parses_final_answer(mock_maritaca):
    requests, replies = mock_maritaca
    replies.append(httpx.Response(200, json=response_json({"valor": 123.45})))

    result = llm.extract_boleto_pdf(b"fake-pdf", filename="boleto.pdf")

    assert result.error is None
    assert isinstance(result.data, llm.BoletoPdfExtraido)
    assert result.data.valor == 123.45
    payload = json.loads(requests[0].content)
    assert payload["model"] == "s5"
    assert payload["service_tier"] == "flex"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "BoletoPdfExtraido"
    assert payload["input"][1]["content"][0]["file"] == {
        "filename": "boleto.pdf",
        "file_data": "data:application/pdf;base64,ZmFrZS1wZGY=",
    }
    assert llm._get_client().timeout == 720


def test_flex_retries_capacity_error_without_switching_tier(mock_maritaca, monkeypatch):
    requests, replies = mock_maritaca
    monkeypatch.setattr("openai._base_client.time.sleep", lambda _: None)
    replies.extend([
        httpx.Response(429, json={"error": {"message": "Flex capacity unavailable"}}),
        httpx.Response(200, json=response_json({"valor": 10})),
    ])

    result = llm.extract_darf_pdf(b"fake-pdf")

    assert result.error is None
    assert result.data.valor == 10
    assert len(requests) == 2
    assert all(json.loads(request.content)["service_tier"] == "flex" for request in requests)


def test_exhausted_flex_returns_extraction_error(mock_maritaca, monkeypatch):
    requests, replies = mock_maritaca
    monkeypatch.setattr("openai._base_client.time.sleep", lambda _: None)
    replies.extend(
        httpx.Response(429, json={"error": {"message": "Flex capacity unavailable"}})
        for _ in range(3)
    )

    result = llm.extract_nf_pdf(b"fake-pdf")

    assert result.data is None
    assert "Flex capacity unavailable" in result.error
    assert len(requests) == 3
    assert all(json.loads(request.content)["service_tier"] == "flex" for request in requests)


def test_overrides_apply_to_text_only_maintenance_analysis(mock_maritaca, monkeypatch):
    requests, replies = mock_maritaca
    monkeypatch.setattr(llm, "DEFAULT_MODEL", "sabia-4-thinking")
    monkeypatch.setattr(llm, "DEFAULT_SERVICE_TIER", "default")
    replies.append(httpx.Response(200, json=response_json({
        "resumo": "Troca de óleo",
        "mudancas": None,
        "motivo_geral": "Manutenção periódica",
    })))

    result = llm.analyze_maintenance({"oficina": "Teste"})

    assert result.error is None
    assert result.data.resumo == "Troca de óleo"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "sabia-4-thinking"
    assert payload["service_tier"] == "default"
    assert [part["type"] for part in payload["input"][1]["content"]] == ["text"]
