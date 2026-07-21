"""Analise textual clinica determinística.

Implementa o algoritmo classico NegEx/ConText (Chapman et al., 2001/2007)
adaptado para portugues: para cada mencao de um termo clinico candidato na
frase, procura por "pistas" (cue phrases) de negacao, temporalidade,
certeza e experienciador dentro de uma janela da propria frase, respeitando
terminadores de escopo ("mas", "porem", ";" etc. interrompem o alcance de
uma pista).

Escopo deliberado e limitacoes desta versao (a documentar honestamente, nao
a esconder):

- O lexico de termos clinicos candidatos (`CLINICAL_TERMS`) e curado
  manualmente a partir do vocabulario clinico de referencia do projeto
  (sintomas de fala e termos gerais de queixa). Nao e exaustivo
  nem versionado como as regras clinicas (`app.rules_engine`) - amadurecer
  esse lexico para producao exigiria o mesmo processo de governanca
  (fonte, aprovacao clinica, versao) usado para `ClinicalRuleSet`.
- E baseado em regras/pistas lexicais, nao em um modelo estatistico ou
  LLM: por isso nao ha "confianca do modelo" a reportar (nao se deve
  usar acuracia para uma inferencia individual) - o campo de proveniencia
  e o metodo determinístico em si (`extraction_method`), auditavel e
  testavel exatamente como as regras clinicas.
- Cada mencao produzida e uma **observacao de modelo** (`FindingNature.
  MODEL_OBSERVATION`), nunca uma classificacao de risco: o motor de
  regras determinístico (`app.rules_engine`) continua sendo a unica fonte
  de risco. Este modulo apenas estrutura o texto livre - nunca decide
  criticidade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Negation(str, Enum):
    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"


class Certainty(str, Enum):
    """Nivel de certeza da mencao clinica: confirmado, suspeito, possivel
    ou condicionado."""

    CONFIRMED = "CONFIRMED"
    SUSPECTED = "SUSPECTED"
    POSSIBLE = "POSSIBLE"
    CONDITIONAL = "CONDITIONAL"


class Temporality(str, Enum):
    CURRENT = "CURRENT"
    PAST = "PAST"
    FUTURE = "FUTURE"


class Experiencer(str, Enum):
    PATIENT = "PATIENT"
    FAMILY_MEMBER = "FAMILY_MEMBER"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ClinicalTextMention:
    """Uma mencao de termo clinico candidato encontrada no texto livre."""

    term: str
    sentence: str
    negation: Negation
    certainty: Certainty
    temporality: Temporality
    experiencer: Experiencer
    start: int
    end: int


# Lexico curado (MVP) - ver limitacoes no docstring do modulo.
CLINICAL_TERMS: tuple[str, ...] = (
    "dor",
    "dor toracica",
    "dor abdominal",
    "febre",
    "tontura",
    "dispneia",
    "falta de ar",
    "taquicardia",
    "bradicardia",
    "cianose",
    "confusao",
    "confusao mental",
    "sonolencia",
    "sudorese",
    "nausea",
    "vomito",
    "convulsao",
    "sangramento",
    "tosse",
    "fraqueza",
    "fadiga",
    "disartria",
    "afasia",
    "desmaio",
    "sincope",
    "hipoglicemia",
    "hiperglicemia",
    "hipotensao",
    "hipertensao",
    "palpitacao",
    "edema",
    "rigidez de nuca",
    "paralisia",
    "formigamento",
)

# Ordenado por comprimento decrescente para que "dor toracica" case antes de "dor".
_SORTED_TERMS = sorted(CLINICAL_TERMS, key=len, reverse=True)

_SCOPE_TERMINATORS = (
    "mas",
    "porem",
    "porém",
    "entretanto",
    "contudo",
    "no entanto",
    "exceto",
    "e",
)

_NEGATION_CUES = (
    "nega",
    "negativo para",
    "negam",
    "ausencia de",
    "ausência de",
    "sem sinais de",
    "sem",
    "nao apresenta",
    "não apresenta",
    "nao ha",
    "não há",
    "nenhum sinal de",
    "descarta",
    "descartado",
    "afastado",
)

_SUSPECTED_CUES = (
    "suspeita de",
    "suspeito de",
    "suspeita-se de",
    "suspeitoso de",
    "sugestivo de",
    "a esclarecer",
    "investigar",
)

_POSSIBLE_CUES = (
    "possivel",
    "possível",
    "possivelmente",
    "pode ser",
    "podem ser",
)

_CONDITIONAL_CUES = (
    "caso apresente",
    "se apresentar",
    "dependendo de",
    "condicionado a",
)

_CONFIRMED_CUES = (
    "confirmado",
    "confirma",
    "diagnosticado com",
    "diagnostico de",
    "diagnóstico de",
)

_PAST_CUES = (
    "ontem",
    "anteriormente",
    "no passado",
    "previo",
    "prévio",
    "historia de",
    "história de",
    "historico de",
    "histórico de",
    "antecedente de",
    "ha dias",
    "há dias",
    "apresentou",
    "teve",
)

_FUTURE_CUES = (
    "ira",
    "irá",
    "podera",
    "poderá",
    "sera",
    "será",
)

_FAMILY_CUES = (
    "historia familiar de",
    "história familiar de",
    "historico familiar de",
    "histórico familiar de",
    "mae",
    "mãe",
    "pai",
    "irmao",
    "irmão",
    "irma",
    "irmã",
    "avo",
    "avô",
    "avó",
    "filho",
    "filha",
    "acompanhante",
    "conjuge",
    "cônjuge",
    "esposa",
    "esposo",
    "familiar",
)


def _strip_accents_lower(text: str) -> str:
    """Normalizacao simples e determinística (sem dependencia de unicodedata
    para tabela de acentos - mapeamento explicito e auditavel)."""
    translation = str.maketrans(
        "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
        "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
    )
    return text.translate(translation).lower()


def _split_sentences(text: str) -> list[tuple[str, int]]:
    """Retorna (frase, offset_no_texto_original) - segmentacao simples por
    pontuacao forte, suficiente para o escopo de pistas de uma frase."""
    sentences: list[tuple[str, int]] = []
    start = 0
    for match in re.finditer(r"[.!?;\n]+", text):
        end = match.start()
        if end > start:
            sentences.append((text[start:end], start))
        start = match.end()
    if start < len(text):
        sentences.append((text[start:], start))
    return sentences


def _cue_scope_ok(normalized_sentence: str, cue_end: int, term_start: int) -> bool:
    """Verifica se nenhum terminador de escopo aparece entre a pista e o termo."""
    between = normalized_sentence[cue_end:term_start]
    for terminator in _SCOPE_TERMINATORS:
        if re.search(rf"\b{re.escape(terminator)}\b", between):
            return False
    return True


def _find_cue_before(
    normalized_sentence: str, term_start: int, cues: tuple[str, ...]
) -> bool:
    for cue in sorted(cues, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(cue)}\b", normalized_sentence):
            if match.end() <= term_start and _cue_scope_ok(
                normalized_sentence, match.end(), term_start
            ):
                return True
    return False


def _find_cue_anywhere(normalized_sentence: str, cues: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"\b{re.escape(cue)}\b", normalized_sentence) for cue in cues
    )


def analyze_clinical_text(text: str) -> list[ClinicalTextMention]:
    """Extrai mencoes de termos clinicos candidatos com negacao, temporalidade,
    certeza e experienciador. Funcao pura, sem I/O.
    """
    if not text:
        return []

    mentions: list[ClinicalTextMention] = []
    for sentence, sentence_offset in _split_sentences(text):
        normalized = _strip_accents_lower(sentence)
        matched_spans: list[tuple[int, int]] = []
        for term in _SORTED_TERMS:
            normalized_term = _strip_accents_lower(term)
            for match in re.finditer(rf"\b{re.escape(normalized_term)}\b", normalized):
                span = (match.start(), match.end())
                # Evita casar "dor" dentro de um span ja coberto por "dor toracica".
                if any(span[0] >= s and span[1] <= e for s, e in matched_spans):
                    continue
                matched_spans.append(span)

                negation = (
                    Negation.NEGATED
                    if _find_cue_before(normalized, span[0], _NEGATION_CUES)
                    else Negation.AFFIRMED
                )
                if _find_cue_anywhere(normalized, _CONDITIONAL_CUES):
                    certainty = Certainty.CONDITIONAL
                elif _find_cue_anywhere(normalized, _SUSPECTED_CUES):
                    certainty = Certainty.SUSPECTED
                elif _find_cue_anywhere(normalized, _POSSIBLE_CUES):
                    certainty = Certainty.POSSIBLE
                else:
                    # CONFIRMED e o padrao (nao a ausencia de sinal, mas a
                    # afirmacao direta - "confirmado"/"diagnosticado" reforcam
                    # o mesmo padrao explicitamente, sem mudar o resultado).
                    certainty = Certainty.CONFIRMED

                if _find_cue_anywhere(normalized, _FUTURE_CUES):
                    temporality = Temporality.FUTURE
                elif _find_cue_anywhere(normalized, _PAST_CUES):
                    temporality = Temporality.PAST
                else:
                    temporality = Temporality.CURRENT

                experiencer = (
                    Experiencer.FAMILY_MEMBER
                    if _find_cue_anywhere(normalized, _FAMILY_CUES)
                    else Experiencer.PATIENT
                )

                mentions.append(
                    ClinicalTextMention(
                        term=term,
                        sentence=sentence.strip(),
                        negation=negation,
                        certainty=certainty,
                        temporality=temporality,
                        experiencer=experiencer,
                        start=sentence_offset + span[0],
                        end=sentence_offset + span[1],
                    )
                )
    return mentions
