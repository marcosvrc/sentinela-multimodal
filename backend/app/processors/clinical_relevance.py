"""Guardrail unico de relevancia clinica de um achado por modalidade
(funcao pura, sem banco/rede) - fonte unica de verdade reaproveitada por:

- `app.clinical_support.service.should_run_automatic_clinical_support`
  (guardrail do apoio a analise clinica automatico via LLM), chamada com
  os campos de um `ModalityFinding` (ORM).
- `app.reports.builder` (calculo do "Nivel de atencao por modalidade" -
  `ModalityAttentionLevel` - exibido na tela de revisao), chamada com os
  campos do dataclass `ReportModalityFinding`.

Recebe `nature`/`quality_metrics` como parametros primitivos (em vez do
objeto `ModalityFinding` inteiro) de proposito: os dois chamadores tem
tipos de achado diferentes (ORM vs. dataclass puro do relatorio) que
carregam os mesmos dois campos relevantes para esta decisao - assim nao
ha acoplamento a nenhum dos dois tipos, e a regra fica testavel isolada.

Extraido de `app.clinical_support.service._finding_is_clinically_relevant`
para nunca haver duas implementacoes divergentes da mesma regra em
lugares diferentes.
"""

from __future__ import annotations

from app.core.enums import FindingNature

# Hipoteses assistidas (`FindingNature.ASSISTED_HYPOTHESIS`) sao SEMPRE
# relevantes por definicao - sao hipoteses sobre um sinal de saude ou o
# proprio contexto de captura clinica (possivel alteracao vocal, possivel
# ausencia de paciente no video), mesmo quando nao confirmadas. Diferente
# de um rotulo generico de objeto (ex.: "chair") que uma deteccao YOLOv8
# pura poderia produzir.
_ASSISTED_HYPOTHESIS_IS_ALWAYS_RELEVANT = True


def is_clinically_relevant(nature: str, quality_metrics: dict | None) -> bool:
    """Decide se UM achado (identificado por `nature` + `quality_metrics`)
    conta como "conteudo clinicamente relevante".

    Regras por natureza/modalidade (documentadas aqui para ficarem
    revisaveis em um unico lugar):

    - `ORIGINAL_DATA` (qualidade estrutural, ex.: "Imagem 300x300", "Texto
      com 40 caracteres"): NUNCA conta sozinho - e so metadado tecnico, nao
      diz nada sobre o CONTEUDO ser clinico.
    - `MODEL_OBSERVATION` de TEXT/AUDIO (termo clinico candidato extraido
      por `app.clinical_nlp.text_analysis`, transcricao com termo
      encontrado): sempre relevante - esses achados so existem quando um
      termo da lista curada de vocabulario clinico foi de fato encontrado
      (o extrator e seguro por construcao, ver `app.clinical_nlp`).
    - `MODEL_OBSERVATION` de audio (analise acustica DSP, ex.:
      "Energia media..."): sempre relevante - e o proprio proposito da
      deteccao de alteracao vocal, nao um enriquecimento generico.
    - `MODEL_OBSERVATION` de IMAGE com rotulos do Azure AI Vision
      (`quality_metrics["clinical_relevance"]` presente, ver
      `app.vision.clinical_relevance`): relevante SOMENTE quando
      `clinical_relevance == "RELEVANT"`. A categorizacao heuristica de
      imagem (PHOTOGRAPH/SCANNED_DOCUMENT/RADIOLOGICAL) e a deteccao de
      sentimento (Azure AI Language) NAO contam sozinhas - a primeira classifica
      qualquer foto (mesmo uma paisagem) em uma categoria, e a segunda e
      so contextual, nunca prova de conteudo clinico.
    - `ASSISTED_HYPOTHESIS` (hipotese de alteracao vocal, hipotese de
      ausencia de pessoa no video): sempre relevante - por definicao sao
      hipoteses sobre um sinal de saude ou o proprio contexto de captura
      clinica, mesmo quando nao confirmadas.
    """
    if nature == FindingNature.ASSISTED_HYPOTHESIS.value:
        return _ASSISTED_HYPOTHESIS_IS_ALWAYS_RELEVANT

    if nature != FindingNature.MODEL_OBSERVATION.value:
        return False

    metrics = quality_metrics or {}

    # Achado de reconhecimento de imagem (Azure AI Vision) - traz sempre
    # a chave "clinical_relevance" (ver app.processors.image); so
    # conta quando explicitamente confirmado como relevante.
    if "clinical_relevance" in metrics:
        return metrics.get("clinical_relevance") == "RELEVANT"

    # Achado de sentimento (Azure AI Language) - sempre contextual, nunca
    # prova de conteudo clinico por si so.
    if "sentiment" in metrics:
        return False

    # Categorizacao heuristica de imagem (cor/textura) - qualquer foto
    # recebe uma categoria, entao nao e evidencia de conteudo clinico.
    if "category" in metrics:
        return False

    # Termo clinico candidato (texto/transcricao) ou analise acustica DSP
    # (energia/pausas/segmentos de fala) - ambos so existem quando ha
    # sinal real (extrator seguro por construcao e proposito da deteccao
    # de alteracao vocal), entao contam como relevantes.
    if "term" in metrics or "rms_energy_mean" in metrics:
        return True

    # Qualquer outro MODEL_OBSERVATION nao mapeado explicitamente acima
    # (ex.: status de transcricao/reconhecimento indisponivel/falho,
    # rascunho de transcricao literal sem termo extraido, deteccao YOLOv8
    # pura sem confirmacao do Azure AI Vision) - conservador: nao conta
    # como prova de relevancia clinica por si so.
    return False
