import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listObservations } from "@/services/api/patients";
import type { Patient } from "@/types/patient";
import { ObservationType } from "@/types/enums.generated";
import { classifyBmi, computeBmi, groupObservationsByType, latestWeightKg } from "@/features/patients/observationConfig";
import styles from "./PatientPersonalDataCard.module.css";

interface PatientPersonalDataCardProps {
  devSubject: string;
  patient: Patient;
}

/**
 * Card somente leitura com os dados pessoais do paciente selecionado,
 * exibido na etapa de selecionar ou confirmar paciente do fluxo de nova
 * analise. O IMC exige o peso mais recente (observacao clinica), por
 * isso ainda consulta `GET
 * /patients/{id}/observations` mesmo sendo so o card de dados pessoais -
 * os DEMAIS dados clinicos (selecao do que entra na analise) ficam em
 * `PatientClinicalDataSelector`, exibido na etapa 2 (modalidades).
 */
export function PatientPersonalDataCard({ devSubject, patient }: PatientPersonalDataCardProps) {
  const observationsQuery = useQuery({
    queryKey: ["observations", patient.id],
    queryFn: () => listObservations(devSubject, patient.id),
    enabled: Boolean(devSubject && patient.id),
  });

  const groupedObservations = useMemo(
    () => groupObservationsByType(observationsQuery.data ?? []),
    [observationsQuery.data],
  );

  const weightKg = latestWeightKg(groupedObservations.get(ObservationType.WEIGHT));
  const bmi = computeBmi(patient.height_cm, weightKg);

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Dados pessoais</h3>
      <dl className={styles.grid}>
        <dt className={styles.term}>Nome</dt>
        <dd className={styles.description}>{patient.full_name}</dd>

        <dt className={styles.term}>Prontuario</dt>
        <dd className={styles.description}>{patient.medical_record_number}</dd>

        <dt className={styles.term}>Idade</dt>
        <dd className={styles.description}>{patient.age} anos</dd>

        <dt className={styles.term}>Sexo registrado</dt>
        <dd className={styles.description}>{patient.registered_sex}</dd>

        <dt className={styles.term}>Data de nascimento</dt>
        <dd className={styles.description}>
          {new Date(patient.birth_date).toLocaleDateString("pt-BR")}
        </dd>

        <dt className={styles.term}>Email</dt>
        <dd className={styles.description}>{patient.email ?? "-"}</dd>

        <dt className={styles.term}>Altura</dt>
        <dd className={styles.description}>
          {patient.height_cm ? `${patient.height_cm} cm` : "Nao informada"}
        </dd>

        <dt className={styles.term}>IMC</dt>
        <dd className={styles.description}>
          {bmi !== null ? `${bmi.toFixed(1)} (${classifyBmi(bmi)})` : "Indisponivel"}
        </dd>
      </dl>
    </div>
  );
}
