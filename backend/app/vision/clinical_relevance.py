"""Guardrail de relevancia clinica para rotulos genericos vindos de
reconhecimento de imagem/video (Amazon Rekognition Image/Video como
ENRIQUECIMENTO opcional, nunca substituindo a heuristica principal).

O Rekognition (`app.integrations.image_recognition`, `app.integrations.
video_recognition`) devolve rotulos GENERICOS de reconhecimento de objeto
("Person", "Car", "Mountain", "Skin" etc.) sem qualquer nocao de relevancia
CLINICA - ele nao sabe distinguir uma fotografia clinica de uma foto de
paisagem. Diferente do processador de TEXTO (`app.clinical_nlp.
text_analysis`), que so gera achado quando encontra um termo de uma lista
curada de vocabulario clinico (e por isso e seguro por construcao), os
rotulos de imagem/video sao abertos e SEM curadoria - por isso precisam
deste guardrail explicito antes de entrarem nas consideracoes finais
(resumo de apoio a analise clinica, `app.clinical_support.service`).

Este modulo e HONESTO sobre sua propria limitacao: e uma heuristica de
lista de palavras-chave, nao um classificador de conteudo clinico treinado
(mesmo principio de `app.vision.image_category`). Quando os rotulos nao
permitem nem confirmar nem descartar relevancia clinica (lista vazia,
servico indisponivel, ou rotulos ambiguos que nao aparecem em nenhuma das
duas listas), o resultado e `relevant=None` ("nao avaliavel") - nunca
`True` por omissao. Tanto `relevant=False` quanto `relevant=None` devem
ser EXCLUIDOS das consideracoes finais (ver `app.clinical_support.
service.generate_analysis_clinical_support_summary`), mas sempre
INFORMADOS ao usuario via o `summary` do achado (nunca descartados em
silencio).
"""

from __future__ import annotations

from dataclasses import dataclass

# Rotulos (em minusculas, ja normalizados) cuja presenca sugere conteudo
# compativel com um contexto clinico - pessoa, parte do corpo, achado
# dermatologico/ferimento ou ambiente/equipamento de saude. Lista curada
# manualmente, deliberadamente conservadora (prefere `None` a um falso
# positivo).
_CLINICALLY_RELEVANT_LABEL_HINTS = frozenset(
    {
        "person",
        "human",
        "skin",
        "face",
        "head",
        "body part",
        "hand",
        "arm",
        "leg",
        "foot",
        "finger",
        "eye",
        "mouth",
        "ear",
        "nose",
        "neck",
        "baby",
        "child",
        "adult",
        "elderly",
        "wound",
        "bandage",
        "bruise",
        "rash",
        "scar",
        "medical equipment",
        "medical",
        "hospital",
        "clinic",
        "x-ray",
        "medicine",
        "medication",
        "doctor",
        "nurse",
        "physician",
        "stethoscope",
        "wheelchair",
        "syringe",
        "pill",
        "bed",
        "patient",
    }
)

# Rotulos cuja presenca sugere conteudo CLARAMENTE sem relacao com contexto
# clinico (objeto, paisagem, ambiente do dia a dia). Tambem deliberadamente
# conservadora - a ausencia de um rotulo daqui nunca implica relevancia
# clinica por si so (ver `_CLINICALLY_RELEVANT_LABEL_HINTS` acima).
_CLEARLY_NON_CLINICAL_LABEL_HINTS = frozenset(
    {
        "car",
        "vehicle",
        "automobile",
        "truck",
        "motorcycle",
        "landscape",
        "mountain",
        "building",
        "architecture",
        "food",
        "meal",
        "animal",
        "pet",
        "dog",
        "cat",
        "furniture",
        "electronics",
        "computer",
        "nature",
        "outdoors",
        "plant",
        "tree",
        "vegetation",
        "sky",
        "beach",
        "ocean",
        "sea",
        "city",
        "urban",
        "road",
        "street",
        "text",
        "logo",
        "symbol",
    }
)


@dataclass(frozen=True)
class ClinicalRelevanceAssessment:
    """`relevant=None` significa "nao avaliavel" (nao tem esse modelo/
    confianca suficiente) - distinto de `False` ("avaliado e descartado").
    Ambos os casos devem ser excluidos das consideracoes finais, mas
    `reason` sempre explica o motivo ao usuario."""

    relevant: bool | None
    reason: str


def assess_label_clinical_relevance(labels: tuple[str, ...]) -> ClinicalRelevanceAssessment:
    """Avalia se os rotulos genericos (Amazon Rekognition) sugerem conteudo
    clinicamente relevante. Heuristica de palavra-chave, nao um
    classificador de conteudo clinico treinado - ver limitacoes no
    docstring do modulo."""
    if not labels:
        return ClinicalRelevanceAssessment(
            relevant=None,
            reason=(
                "Nenhum rotulo foi identificado - nao ha base para confirmar relevancia "
                "clinica deste conteudo."
            ),
        )

    normalized = {label.strip().lower() for label in labels}

    if normalized & _CLINICALLY_RELEVANT_LABEL_HINTS:
        return ClinicalRelevanceAssessment(
            relevant=True,
            reason=(
                "Ao menos um rotulo identificado sugere conteudo compativel com contexto "
                "clinico (pessoa, parte do corpo ou ambiente de saude)."
            ),
        )

    if normalized & _CLEARLY_NON_CLINICAL_LABEL_HINTS:
        return ClinicalRelevanceAssessment(
            relevant=False,
            reason=(
                "Os rotulos identificados sugerem conteudo sem relacao com contexto clinico "
                "(ex: objeto, paisagem ou ambiente do dia a dia) - nao sera considerado nas "
                "consideracoes finais desta analise."
            ),
        )

    return ClinicalRelevanceAssessment(
        relevant=None,
        reason=(
            "Os rotulos identificados nao permitem confirmar nem descartar relevancia "
            "clinica deste conteudo com as heuristicas atuais - nao sera considerado nas "
            "consideracoes finais desta analise."
        ),
    )
