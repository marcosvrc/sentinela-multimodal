"""Testes do adaptador real de LLM via Amazon Bedrock
(`app.integrations.llm.bedrock_adapter.BedrockLlmAdapter`).

Mesmo padrao de `test_image_recognition_adapters.py`: um cliente
`bedrock-runtime` FALSO e injetado (via monkeypatch em `boto3.client`,
unico ponto onde o adaptador toca a rede), verificando a construcao da
requisicao Converse (schema/system/mensagem) e o parsing da resposta -
sem depender de credenciais/rede AWS real."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.integrations.llm.base import (
    LlmAnalysisClinicalSupportRequest,
    LlmAnalysisModalityFindingInput,
    LlmAnalysisStructuredInputInput,
    LlmClinicalAlertSummaryInput,
    LlmClinicalObservationSummaryInput,
    LlmClinicalSupportRequest,
    LlmModalitySummaryInput,
    LlmSummaryRequest,
)
from app.integrations.llm.bedrock_adapter import BedrockLlmAdapter


def _fake_converse_response(payload: dict) -> dict:
    return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}


class _FakeBedrockClient:
    def __init__(self, response_payload: dict):
        self._response_payload = response_payload
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return _fake_converse_response(self._response_payload)


def _make_adapter(fake_client: _FakeBedrockClient) -> BedrockLlmAdapter:
    with patch("boto3.client", return_value=fake_client):
        return BedrockLlmAdapter(region="us-east-1", model_id="anthropic.claude-3-5-sonnet-test")


def test_summarize_sends_converse_request_with_json_schema_output_config() -> None:
    fake_client = _FakeBedrockClient(
        {"summary_text": "Nivel 6, hipoxemia grave.", "uncertainty_note": "Revisar."}
    )
    adapter = _make_adapter(fake_client)

    request = LlmSummaryRequest(
        risk_outcome="MATCHED",
        risk_level=6,
        risk_classification_label="Hipoxemia grave",
        inconclusive_reason=None,
        matched_rule_codes=("spo2",),
        modality_summaries=(
            LlmModalitySummaryInput(
                modality_type="IMAGE", quality_state="ADEQUATE", summary="Imagem 800x600."
            ),
        ),
    )

    result = adapter.summarize(request)

    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["modelId"] == "anthropic.claude-3-5-sonnet-test"
    assert call["system"][0]["text"].startswith("Voce sintetiza")
    assert "<dados_nao_confiaveis>" in call["messages"][0]["content"][0]["text"]

    output_format = call["outputConfig"]["textFormat"]
    assert output_format["type"] == "json_schema"
    schema = json.loads(output_format["structure"]["jsonSchema"]["schema"])
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"summary_text", "uncertainty_note"}
    # O schema NUNCA inclui campos de risco - o Bedrock fisicamente nao
    # consegue devolver um `risk_level` alternativo (mesma garantia do
    # adaptador OpenAI via response_format json_schema strict).
    assert "risk_level" not in schema["properties"]

    assert result.summary_text == "Nivel 6, hipoxemia grave."
    assert result.uncertainty_note == "Revisar."
    assert result.provider == "bedrock"
    assert result.model == "anthropic.claude-3-5-sonnet-test"
    assert result.prompt_version == "bedrock-consolidation-v1"
    assert len(result.input_hash) == 64
    assert len(result.output_hash) == 64


def test_generate_clinical_support_summary_parses_all_four_sections() -> None:
    fake_client = _FakeBedrockClient(
        {
            "summary_text": "Paciente com 68 anos.",
            "probable_causes": "Possivel infeccao respiratoria.",
            "suggested_next_steps": "Avaliacao presencial.",
            "uncertainty_note": "Apoio, nao substitui avaliacao medica.",
        }
    )
    adapter = _make_adapter(fake_client)

    request = LlmClinicalSupportRequest(
        patient_age=68,
        patient_sex="feminino",
        observations=(
            LlmClinicalObservationSummaryInput(
                observation_type="SPO2", unit="%", recent_values=(("91", "2026-07-17T10:00:00Z"),)
            ),
        ),
        alerts=(
            LlmClinicalAlertSummaryInput(
                signal_key="spo2_drop",
                severity="HIGH",
                status="OPEN",
                expected_action="Avaliar paciente",
                detected_at="2026-07-17T10:05:00Z",
            ),
        ),
    )

    result = adapter.generate_clinical_support_summary(request)

    call = fake_client.calls[0]
    assert call["system"][0]["text"].startswith("Voce e um assistente de apoio")
    output_format = call["outputConfig"]["textFormat"]
    schema = json.loads(output_format["structure"]["jsonSchema"]["schema"])
    assert set(schema["required"]) == {
        "summary_text",
        "probable_causes",
        "suggested_next_steps",
        "uncertainty_note",
    }

    assert result.summary_text == "Paciente com 68 anos."
    assert result.probable_causes == "Possivel infeccao respiratoria."
    assert result.suggested_next_steps == "Avaliacao presencial."
    assert result.provider == "bedrock"
    assert result.prompt_version == "bedrock-clinical-support-v1"


def test_generate_analysis_clinical_support_summary_correlates_findings() -> None:
    fake_client = _FakeBedrockClient(
        {
            "summary_text": "Analise com risco moderado.",
            "probable_causes": "Achados de imagem e dados clinicos convergem.",
            "suggested_next_steps": "Revisar achados por modalidade.",
            "uncertainty_note": "Apoio, nao substitui avaliacao medica.",
        }
    )
    adapter = _make_adapter(fake_client)

    request = LlmAnalysisClinicalSupportRequest(
        patient_age=54,
        patient_sex="masculino",
        risk_outcome="MATCHED",
        risk_level=3,
        risk_classification_label="Moderado",
        structured_inputs=(
            LlmAnalysisStructuredInputInput(code="spo2", inputs={"spo2_percent": 91}),
        ),
        findings=(
            LlmAnalysisModalityFindingInput(
                modality_type="IMAGE",
                nature="MODEL_OBSERVATION",
                quality_state="ADEQUATE",
                summary="Categoria candidata: PHOTOGRAPH.",
            ),
        ),
    )

    result = adapter.generate_analysis_clinical_support_summary(request)

    call = fake_client.calls[0]
    message_text = call["messages"][0]["content"][0]["text"]
    payload = json.loads(message_text.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert payload["risk_level"] == 3
    assert payload["findings"][0]["modality_type"] == "IMAGE"
    assert payload["structured_inputs"][0]["code"] == "spo2"

    assert result.provider == "bedrock"
    assert result.prompt_version == "bedrock-analysis-clinical-support-v1"


def test_adapter_uses_boto3_bedrock_runtime_client_with_configured_region() -> None:
    with patch("boto3.client") as mock_boto3_client:
        mock_boto3_client.return_value = MagicMock()
        BedrockLlmAdapter(region="us-east-1", model_id="some-model")

    mock_boto3_client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")
