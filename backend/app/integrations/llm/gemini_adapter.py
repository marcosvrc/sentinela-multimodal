"""Placeholder do adaptador de LLM via Google Gemini - AINDA NAO
IMPLEMENTADO.

Registrado na tela de feature flags (`/admin/feature-flags`) para
planejamento (o administrador pode ja escolher "Gemini" como provedor
preferido e o modelo desejado), mas nao existe integracao real: qualquer
metodo chamado aqui levanta `NotImplementedError` explicito. Isso segue a
mesma disciplina de honestidade do resto do projeto (`LocalUnavailable
VisionAdapter`, `LocalUnavailableTranscriptionAdapter`) - nunca fingir que
uma integracao funciona.

`app.integrations.llm.get_llm_adapter` NUNCA instancia esta classe hoje -
ele falha direto com uma mensagem explicativa antes de chegar aqui,
porque nao ha nada de utilidade adicional em construir o objeto so para
falhar no primeiro metodo chamado. Este arquivo existe principalmente
para documentar o proximo passo de implementacao (mesmo padrao de
`AwsTranscribeAdapter`/`OpenAiLlmAdapter`: encapsular o SDK do provedor,
aqui seria `google-generativeai` ou `google-genai`) e para dar um ponto
de extensao unico quando a integracao for priorizada.
"""

from __future__ import annotations

from app.integrations.llm.base import (
    LlmAnalysisClinicalSupportRequest,
    LlmClinicalSupportRequest,
    LlmClinicalSupportResult,
    LlmSummaryRequest,
    LlmSummaryResult,
)

_NOT_IMPLEMENTED_MESSAGE = (
    "Integracao com Google Gemini ainda nao foi implementada neste projeto. "
    "Este e um placeholder registrado na tela de feature flags para planejamento."
)


class GeminiLlmAdapter:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def summarize(self, request: LlmSummaryRequest) -> LlmSummaryResult:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def generate_clinical_support_summary(
        self, request: LlmClinicalSupportRequest
    ) -> LlmClinicalSupportResult:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def generate_analysis_clinical_support_summary(
        self, request: LlmAnalysisClinicalSupportRequest
    ) -> LlmClinicalSupportResult:
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)
