"""Popula a base com 50 pacientes ficticios (dados sinteticos - nunca
dados reais, ESCOPO_PROJETO.md secao 8.2), cada um com observacoes
clinicas em TODOS os tipos hoje suportados pelo formulario de registro
(`frontend/src/features/patients/observationConfig.py::CREATABLE_OBSERVATION_TYPES`):
Saturacao (SpO2), Frequencia cardiaca, Frequencia respiratoria,
Temperatura corporal, Pressao arterial, Glicemia capilar e Peso. Dor e
nivel de consciencia ficam fora deste seed porque ainda nao tem
formulario/grafico dedicado na tela de paciente. Altura e preenchida
direto no cadastro do paciente (`Patient.height_cm`), nao como observacao
repetida no tempo.

Cada paciente recebe exatamente 10 registros de cada um dos 7 tipos acima
(70 observacoes por paciente, uma por dia nos ultimos 10 dias), com valores
sorteados dentro de uma faixa que reflete um dos quatro perfis clinicos
pedidos (referencia: docs/CLASSIFICACAO_DADOS_CLINICOS.md):

    - 20 pacientes "saudavel"      (faixa normal de todos os sinais)
    - 10 pacientes "moderado"      (alteracao leve/moderada)
    - 10 pacientes "critico"       (alteracao alta)
    - 10 pacientes "super_critico" (alteracao critica/grave)

Altura e peso (e portanto o IMC resultante, docs/CLASSIFICACAO_DADOS_CLINICOS.md
secao 12) seguem uma classificacao de criticidade PROPRIA, com apenas 3
niveis (nao 4, diferente dos sinais vitais acima) - reaproveitando o mesmo
agrupamento de pacientes por simplicidade e rastreabilidade:

    - baixa criticidade de IMC:  pacientes "saudavel"      -> IMC normal (18.5-24.9)
    - criticidade moderada:      pacientes "moderado"      -> IMC sobrepeso (25.0-29.9)
    - alta criticidade:          pacientes "critico" e
                                  "super_critico"           -> IMC obesidade grau II/III (35.0-42.0)

A altura e sorteada uma vez por paciente (faixa por sexo registrado) e
preenchida via `PatientUpdate` para quem ainda nao a tem; o peso de cada um
dos 10 registros varia levemente (~1.5%) em torno do IMC-alvo do paciente,
simulando a flutuacao natural de peso no dia a dia.

O autor de cada observacao e sorteado entre os funcionarios clinicos ja
cadastrados (ver `make seed-employees`) no formato "matricula - nome"
(mesmo padrao adotado no campo pesquisavel de funcionario do popup de
observacao). Cada paciente tambem recebe vinculo assistencial ativo com
todos os medicos/enfermeiros ativos da instituicao, para que qualquer
usuario de desenvolvimento clinico consiga abrir o prontuario pela tela
sem precisar criar o vinculo manualmente.

Idempotente: o identificador institucional/prontuario e deterministico
(`SEED-PAT-0001`..`SEED-PAT-0050`); reexecutar o script reaproveita
pacientes existentes e so completa altura/observacoes/vinculos que ainda
faltarem (contagem por tipo, nunca duplica; altura so e preenchida se
ainda estiver vazia).

Uso:
    uv run python -m scripts.seed_patients
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.administration import service as administration_service
from app.api.schemas.observations import ObservationCreate
from app.api.schemas.patients import PatientCreate, PatientUpdate
from app.core.db import SessionLocal
from app.core.enums import ObservationType
from app.identity import service as identity_service
from app.observations import service as observations_service
from app.observations.models import ClinicalObservation
from app.patients import service as patients_service
from app.patients.models import Patient

DEV_INSTITUTION_NAME = "Instituicao de Desenvolvimento"
SEED_ACTOR = "seed-patients-script"

PATIENT_COUNT = 50
OBSERVATIONS_PER_TYPE = 10

# Ordem fixa de blocos por perfil - paciente 1-20 saudavel, 21-30 moderado,
# 31-40 critico, 41-50 super_critico (facilita localizar cada grupo pelo
# prontuario SEED-PAT-XXXX ao validar o seed).
PROFILE_BLOCKS: list[tuple[str, int]] = [
    ("saudavel", 20),
    ("moderado", 10),
    ("critico", 10),
    ("super_critico", 10),
]

FIRST_NAMES_MALE = [
    "Pedro", "Miguel", "Arthur", "Heitor", "Davi", "Bernardo", "Theo",
    "Gabriel", "Samuel", "Enzo", "Guilherme", "Nicolas", "Lucas", "Mateus",
    "Rafael", "Vinicius", "Caio", "Igor", "Otavio", "Renato", "Sergio",
    "Fabio", "Diego", "Alexandre", "Ricardo",
]
FIRST_NAMES_FEMALE = [
    "Alice", "Sophia", "Helena", "Valentina", "Laura", "Isabella", "Manuela",
    "Giovanna", "Julia", "Luiza", "Heloisa", "Livia", "Lorena", "Clara",
    "Rafaela", "Yasmin", "Vitoria", "Melissa", "Rita", "Debora", "Simone",
    "Cristina", "Renata", "Elaine", "Priscila",
]
LAST_NAMES = [
    "Araujo", "Cardoso", "Correia", "Duarte", "Farias", "Freitas", "Gonçalves",
    "Guimaraes", "Junqueira", "Leite", "Macedo", "Mendes", "Monteiro", "Nogueira",
    "Pinto", "Ramos", "Sales", "Siqueira", "Teixeira", "Vasconcelos", "Xavier",
    "Braga", "Cavalcante", "Peixoto", "Tavares",
]

# --- Faixas de valor por perfil clinico -------------------------------------
# Referencia direcional: docs/CLASSIFICACAO_DADOS_CLINICOS.md (tabelas de
# classificacao por sinal). Os quatro perfis aqui NAO sao os mesmos seis
# niveis de risco do documento (que variam por sinal) - sao uma
# simplificacao proposital em 4 faixas amplas (saudavel/moderado/critico/
# super_critico), sempre dentro do limite fisiologicamente possivel
# validado por `app.observations.validation` (nunca gera valor que a API
# rejeitaria).

_NumRange = tuple[float, float]

SPO2_RANGES: dict[str, _NumRange] = {
    "saudavel": (96, 99),
    "moderado": (94, 95),
    "critico": (89, 93),
    "super_critico": (80, 88),
}
HEART_RATE_RANGES: dict[str, _NumRange] = {
    "saudavel": (65, 95),
    "moderado": (101, 109),
    "critico": (112, 130),
    "super_critico": (135, 170),
}
RESPIRATORY_RATE_RANGES: dict[str, _NumRange] = {
    "saudavel": (14, 19),
    "moderado": (21, 23),
    "critico": (25, 29),
    "super_critico": (32, 40),
}
TEMPERATURE_RANGES: dict[str, _NumRange] = {
    "saudavel": (36.2, 37.3),
    "moderado": (37.6, 38.3),
    "critico": (38.6, 39.5),
    "super_critico": (39.8, 40.8),
}
# (sistolica_min, sistolica_max, diastolica_min, diastolica_max)
BLOOD_PRESSURE_RANGES: dict[str, tuple[float, float, float, float]] = {
    "saudavel": (110, 118, 65, 78),
    "moderado": (130, 139, 82, 88),
    "critico": (150, 175, 95, 115),
    "super_critico": (185, 215, 125, 140),
}
GLYCEMIA_RANGES: dict[str, _NumRange] = {
    "saudavel": (75, 98),
    "moderado": (105, 124),
    "critico": (260, 350),
    "super_critico": (420, 480),
}

# Altura sorteada por sexo registrado (faixa adulta plausivel, cm) -
# independente do perfil de criticidade: a altura em si nao e um sinal de
# risco, e apenas o insumo (junto com o peso) para calcular o IMC.
HEIGHT_RANGE_CM_BY_SEX: dict[str, _NumRange] = {
    "feminino": (155, 172),
    "masculino": (165, 190),
}

# IMC-alvo por perfil de criticidade (docs/CLASSIFICACAO_DADOS_CLINICOS.md
# secao 12, tabela da OMS) - usado para calcular o peso a partir da altura
# ja sorteada do paciente (peso = imc_alvo * altura_m^2), com uma pequena
# variacao (~1.5%) entre os 10 registros para simular flutuacao natural.
# "critico" e "super_critico" (sinais vitais) compartilham a mesma faixa
# de alta criticidade de IMC - o pedido distinguia apenas 3 niveis de IMC
# (baixa/moderada/alta), nao 4.
BMI_TARGET_RANGE_BY_PROFILE: dict[str, _NumRange] = {
    "saudavel": (19.0, 24.5),  # baixa criticidade de IMC: peso normal
    "moderado": (26.0, 29.5),  # criticidade moderada: sobrepeso
    "critico": (35.5, 39.5),  # alta criticidade: obesidade grau II
    "super_critico": (35.5, 39.5),  # alta criticidade: obesidade grau II
}
# Contexto obrigatorio de glicemia (app.observations.validation) por
# perfil: perfis alterados assumem paciente diabetico em uso de insulina,
# coerente com o valor de glicemia sorteado.
GLYCEMIA_CONTEXT_BY_PROFILE: dict[str, dict[str, object]] = {
    "saudavel": {"moment": "jejum", "patient_type": "nao_diabetico", "insulin_use": False},
    "moderado": {"moment": "jejum", "patient_type": "nao_diabetico", "insulin_use": False},
    "critico": {"moment": "jejum", "patient_type": "diabetico", "insulin_use": True},
    "super_critico": {"moment": "jejum", "patient_type": "diabetico", "insulin_use": True},
}


def _generate_full_names(count: int) -> list[tuple[str, str]]:
    """Retorna `count` pares (nome_completo, sexo_registrado) unicos."""
    rng = random.Random("sentinelhealth-seed-patients-names")
    combos: set[tuple[str, str]] = set()
    while len(combos) < count:
        is_female = rng.random() < 0.5
        first = rng.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
        last_1, last_2 = rng.sample(LAST_NAMES, 2)
        full_name = f"{first} {last_1} {last_2}"
        sex = "feminino" if is_female else "masculino"
        combos.add((full_name, sex))
    return sorted(combos)


def _generate_birth_date(rng: random.Random) -> date:
    age_years = rng.randint(19, 88)
    today = date.today()
    try:
        return today.replace(year=today.year - age_years)
    except ValueError:
        # 29 de fevereiro em ano sem 29/02 no ano de nascimento resultante.
        return today.replace(year=today.year - age_years, day=28)


def _round_to_step(value: float, step: float) -> float:
    return round(value / step) * step


def _observation_value(
    observation_type: ObservationType, profile: str, rng: random.Random
) -> tuple[dict[str, float], str, dict[str, object]]:
    """Retorna (value, unit, context) para um tipo/perfil, com pequena
    variacao aleatoria dentro da faixa do perfil."""
    if observation_type is ObservationType.SPO2:
        low, high = SPO2_RANGES[profile]
        return {"value": round(rng.uniform(low, high))}, "%", {}
    if observation_type is ObservationType.HEART_RATE:
        low, high = HEART_RATE_RANGES[profile]
        return {"value": round(rng.uniform(low, high))}, "bpm", {}
    if observation_type is ObservationType.RESPIRATORY_RATE:
        low, high = RESPIRATORY_RATE_RANGES[profile]
        return {"value": round(rng.uniform(low, high))}, "irpm", {}
    if observation_type is ObservationType.TEMPERATURE:
        low, high = TEMPERATURE_RANGES[profile]
        return {"value": round(rng.uniform(low, high), 1)}, "celsius", {}
    if observation_type is ObservationType.GLYCEMIA:
        low, high = GLYCEMIA_RANGES[profile]
        context = dict(GLYCEMIA_CONTEXT_BY_PROFILE[profile])
        return {"value": round(rng.uniform(low, high))}, "mg/dL", context
    if observation_type is ObservationType.BLOOD_PRESSURE:
        sys_low, sys_high, dia_low, dia_high = BLOOD_PRESSURE_RANGES[profile]
        systolic = round(rng.uniform(sys_low, sys_high))
        diastolic = round(rng.uniform(dia_low, dia_high))
        return {"systolic": systolic, "diastolic": diastolic}, "mmHg", {}
    raise ValueError(f"Tipo de observacao sem faixa de perfil definida: {observation_type}")


def _generate_height_cm(sex: str, rng: random.Random) -> float:
    low, high = HEIGHT_RANGE_CM_BY_SEX.get(sex, HEIGHT_RANGE_CM_BY_SEX["feminino"])
    return round(rng.uniform(low, high), 1)


def _weight_value_kg(height_cm: float, profile: str, rng: random.Random) -> dict[str, float]:
    """Peso (kg) que produz o IMC-alvo do perfil para a altura do paciente,
    com uma pequena variacao (~1.5%) para simular flutuacao de peso entre
    os 10 registros - nunca o mesmo valor exato repetido 10 vezes."""
    low, high = BMI_TARGET_RANGE_BY_PROFILE[profile]
    target_bmi = rng.uniform(low, high)
    height_m = height_cm / 100
    base_weight = target_bmi * height_m * height_m
    jittered = base_weight * rng.uniform(0.985, 1.015)
    return {"value": round(jittered, 1)}


OBSERVATION_TYPES: list[ObservationType] = [
    ObservationType.SPO2,
    ObservationType.HEART_RATE,
    ObservationType.RESPIRATORY_RATE,
    ObservationType.TEMPERATURE,
    ObservationType.BLOOD_PRESSURE,
    ObservationType.GLYCEMIA,
]


def _existing_observation_count(
    session, institution_id: uuid.UUID, patient_id: uuid.UUID, observation_type: ObservationType
) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(ClinicalObservation)
            .where(
                ClinicalObservation.institution_id == institution_id,
                ClinicalObservation.patient_id == patient_id,
                ClinicalObservation.observation_type == observation_type.value,
            )
        )
        or 0
    )


def _get_or_create_patient(
    session, institution_id: uuid.UUID, mrn: str, full_name: str, sex: str, rng: random.Random
) -> tuple[Patient, bool]:
    existing = session.scalar(
        select(Patient).where(
            Patient.institution_id == institution_id, Patient.medical_record_number == mrn
        )
    )
    if existing is not None:
        return existing, False

    local_part = full_name.lower().replace(" ", ".")
    data = PatientCreate(
        medical_record_number=mrn,
        full_name=full_name,
        birth_date=_generate_birth_date(rng),
        registered_sex=sex,
        email=f"{local_part}@example.com",
    )
    patient = patients_service.create_patient(session, institution_id, data, actor=SEED_ACTOR)
    return patient, True


def main() -> None:
    session = SessionLocal()
    try:
        institution = identity_service.get_or_create_institution(session, DEV_INSTITUTION_NAME)
        session.commit()
        session.refresh(institution)
        print(f"Instituicao: {institution.id} ({institution.name})")

        employees, _ = administration_service.list_employees(
            session, institution.id, page=1, page_size=200, active=True
        )
        authors = [e for e in employees if e.user_id is not None]
        if not authors:
            print(
                "Nenhum funcionario com conta de acesso encontrado. Rode antes "
                "'make seed-employees' para ter autores disponiveis para as observacoes."
            )
            return

        care_staff = identity_service.list_clinical_staff(session, institution.id)
        if not care_staff:
            print(
                "Nenhum medico/enfermeiro ativo encontrado. Rode antes "
                "'make seed-dev-data' e/ou 'make seed-employees'."
            )
            return

        full_names = _generate_full_names(PATIENT_COUNT)
        profile_by_index: list[str] = []
        for profile, count in PROFILE_BLOCKS:
            profile_by_index.extend([profile] * count)

        author_rng = random.Random("seed-patients-authors")

        created_patients = 0
        reused_patients = 0
        created_observations = 0
        created_assignments = 0
        updated_heights = 0

        now = datetime.now(timezone.utc)

        for index, ((full_name, sex), profile) in enumerate(
            zip(full_names, profile_by_index, strict=True), start=1
        ):
            mrn = f"SEED-PAT-{index:04d}"
            patient_rng = random.Random(f"seed-patient-{index}")
            patient, was_created = _get_or_create_patient(
                session, institution.id, mrn, full_name, sex, patient_rng
            )
            if was_created:
                created_patients += 1
            else:
                reused_patients += 1

            if patient.height_cm is None:
                height_cm = _generate_height_cm(sex, patient_rng)
                patients_service.update_patient(
                    session,
                    institution.id,
                    patient.id,
                    PatientUpdate(height_cm=height_cm),
                    actor=SEED_ACTOR,
                )
                updated_heights += 1
            else:
                height_cm = float(patient.height_cm)

            for observation_type in OBSERVATION_TYPES:
                existing_count = _existing_observation_count(
                    session, institution.id, patient.id, observation_type
                )
                missing = OBSERVATIONS_PER_TYPE - existing_count
                if missing <= 0:
                    continue
                # Preenche do mais antigo (dia -missing) ao mais recente
                # (dia -1), sempre completando os dias que ainda faltam -
                # reexecucoes parciais nunca duplicam os dias ja gravados.
                for day_offset in range(existing_count, OBSERVATIONS_PER_TYPE):
                    value, unit, context = _observation_value(
                        observation_type, profile, patient_rng
                    )
                    author = author_rng.choice(authors)
                    measured_at = now - timedelta(
                        days=OBSERVATIONS_PER_TYPE - day_offset, minutes=patient_rng.randint(0, 90)
                    )
                    data = ObservationCreate(
                        observation_type=observation_type,
                        value=value,
                        unit=unit,
                        context=context,
                        measured_at=measured_at,
                        origin="seed-script",
                        author=f"{author.registration_number} - {author.full_name}",
                    )
                    observations_service.create_observation(
                        session, institution.id, patient.id, data, SEED_ACTOR
                    )
                    created_observations += 1

            # Peso: faixa dependente da altura do proprio paciente (IMC-alvo
            # por perfil de criticidade), por isso fora de `OBSERVATION_TYPES`/
            # `_observation_value` (que so cobrem sinais com uma faixa fixa
            # por perfil, independente do paciente).
            existing_weight_count = _existing_observation_count(
                session, institution.id, patient.id, ObservationType.WEIGHT
            )
            for day_offset in range(existing_weight_count, OBSERVATIONS_PER_TYPE):
                author = author_rng.choice(authors)
                measured_at = now - timedelta(
                    days=OBSERVATIONS_PER_TYPE - day_offset, minutes=patient_rng.randint(0, 90)
                )
                data = ObservationCreate(
                    observation_type=ObservationType.WEIGHT,
                    value=_weight_value_kg(height_cm, profile, patient_rng),
                    unit="kg",
                    context={},
                    measured_at=measured_at,
                    origin="seed-script",
                    author=f"{author.registration_number} - {author.full_name}",
                )
                observations_service.create_observation(
                    session, institution.id, patient.id, data, SEED_ACTOR
                )
                created_observations += 1

            for user in care_staff:
                if not identity_service.has_active_assignment(
                    session,
                    institution_id=institution.id,
                    user_id=user.id,
                    patient_id=patient.id,
                ):
                    identity_service.create_patient_care_assignment(
                        session,
                        institution_id=institution.id,
                        patient_id=patient.id,
                        user_id=user.id,
                        care_unit_id=None,
                        assigned_by=SEED_ACTOR,
                    )
                    created_assignments += 1
            session.commit()

            print(f"  [{profile:<14}] {mrn}  {full_name}")

        print()
        print(
            f"Pacientes: {created_patients} criados, {reused_patients} ja existiam "
            f"(total {PATIENT_COUNT})."
        )
        print(f"Alturas preenchidas nesta execucao: {updated_heights}.")
        print(f"Observacoes clinicas criadas nesta execucao: {created_observations}.")
        print(f"Vinculos assistenciais criados nesta execucao: {created_assignments}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
