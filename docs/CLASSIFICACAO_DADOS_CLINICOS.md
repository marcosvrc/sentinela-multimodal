# Classificação de Dados Clínicos — Base de Conhecimento

> **Status:** referência preliminar para o MVP, sujeita à validação e aprovação clínica formal. Não deve ser usada isoladamente para diagnóstico, prescrição ou conduta automática.

## Propósito

Este documento define a taxonomia canônica e regras preliminares para classificar sinais vitais, sintomas e achados multimodais. Deve ser utilizado para:

1. Receber um valor medido ou observação clínica
2. Identificar a faixa/categoria correspondente na tabela do sinal
3. Retornar a classificação e o nível de risco associado
4. Sugerir a conduta sistêmica e o protocolo institucional aplicável
5. Registrar evidência, contexto, versão da regra e limitações

As faixas isoladas não substituem avaliação clínica nem equivalem automaticamente a diagnóstico ou pontuação NEWS2. O motor deve distinguir valor fisiológico, pontuação de protocolo, risco agudo, risco crônico e decisão do profissional.

---

## Níveis de Risco — Definição Global

| Código | Nível | Significado | Conduta sistêmica mínima |
| ---: | --- | --- | --- |
| 1 | Baixo | Sem alteração relevante pela regra aplicada | Registrar e seguir rotina |
| 2 | Leve | Alteração discreta | Acompanhar ou repetir medição |
| 3 | Moderado | Alteração que requer avaliação | Solicitar avaliação clínica |
| 4 | Alto | Alteração significativa | Alertar equipe assistencial |
| 5 | Muito alto | Alteração grave | Solicitar intervenção prioritária |
| 6 | Crítico | Possível emergência | Seguir protocolo institucional de emergência |

**Inconclusivo** é um estado técnico, não um nível de risco. Deve ser usado quando dados obrigatórios estiverem ausentes, inválidos, conflitantes ou abaixo do limiar mínimo de qualidade. Um resultado inconclusivo nunca poderá ser convertido automaticamente em baixo risco.

### Regra Geral de Consolidação

- A criticidade consolidada será calculada pelo motor determinístico aprovado, não pelo LLM.
- A regra de “usar sempre o maior risco” só vale quando explicitamente indicada pelo protocolo; sinais independentes não devem ser somados ou maximizados sem regra validada.
- A presença de sintomas de alarme pode elevar a prioridade independentemente do valor isolado.
- A saída deve informar: valor original, unidade, contexto, classificação fisiológica, nível, regra, fonte, versão e evidência.
- Alterações feitas pelo profissional não apagam a classificação original.

### Contexto Mínimo de Toda Medição

| Campo | Requisito |
| --- | --- |
| Data e hora | Obrigatório |
| Origem e autor | Obrigatório |
| Unidade e método/equipamento | Obrigatório quando aplicável |
| População/protocolo | Adulto no MVP; exceções exigem protocolo próprio |
| Qualidade da leitura | Válida, duvidosa ou inválida |
| Condições relevantes | Repouso, posição, oxigênio, alimentação e outras conforme o sinal |

---

## Índice de Seções

| #  | Seção                            | Tipo           |
| -- | -------------------------------- | -------------- |
| 1  | Pressão Arterial                 | Sinal vital    |
| 2  | Saturação de Oxigênio (SpO₂)    | Sinal vital    |
| 3  | Frequência Cardíaca              | Sinal vital    |
| 4  | Frequência Respiratória          | Sinal vital    |
| 5  | Temperatura Corporal             | Sinal vital    |
| 6  | Glicemia Capilar                 | Sinal vital    |
| 7  | Nível de Consciência             | Avaliação      |
| 8  | Dor                              | Avaliação      |
| 9  | Sintomas Relacionados à Fala     | Observação     |
| 10 | Sintomas Relacionados ao Movimento | Observação   |
| 11 | Análise Relacionada a Cirurgias  | Multimodal     |
| 12 | Índice de Massa Corporal (IMC)   | Antropometria  |

---

## 1. Pressão Arterial

**Unidade:** mmHg  
**Formato:** sistólica/diastólica (ex: 120/80)

### Tabela de Classificação Preliminar — Adulto

| Classificação         | Condição Sistólica | Condição Diastólica | Risco    |
| --------------------- | -----------------: | ------------------: | -------- |
| Hipotensão grave      | ≤ 90               | —                   | Crítico  |
| Hipotensão            | 91–100             | —                   | Alto     |
| Limítrofe baixa       | 101–110            | —                   | Moderado |
| Normal                | 111–119            | < 80                | Baixo    |
| Pressão elevada       | 120–129            | < 80                | Moderado |
| Hipertensão estágio 1 | 130–139            | 80–89               | Moderado |
| Hipertensão estágio 2 | 140–180            | 90–120              | Alto     |
| Crise hipertensiva    | > 180              | > 120               | Crítico  |

### Regras de Decisão

- **Normal** e **Pressão elevada**: ambas as condições devem ser satisfeitas (sistólica E diastólica).
- Nas categorias hipertensivas, prevalece a categoria mais elevada atingida pela sistólica **ou** pela diastólica.
- **Regra de conflito:** quando sistólica e diastólica caem em classificações diferentes, utilizar sempre a de MAIOR risco.
- NEWS2 hospitalar: sistólica ≤ 90 ou ≥ 220 mmHg = pontuação máxima de anormalidade.

> A classificação acima é uma regra preliminar de triagem. “Crise hipertensiva” e “hipotensão grave” exigem correlação com sintomas, repetição da medida quando segura e protocolo institucional; a tabela não estabelece diagnóstico isoladamente.

---

## 2. Saturação de Oxigênio (SpO₂)

**Unidade:** %  
**Escala padrão:** adultos sem doença respiratória crônica

### Tabela de Classificação — Escala Padrão

| Classificação      | Faixa  | Risco    |
| ------------------ | -----: | -------- |
| Normal             | ≥ 96   | Baixo    |
| Levemente reduzida | 94–95  | Moderado |
| Hipoxemia          | 92–93  | Alto     |
| Hipoxemia grave    | ≤ 91   | Crítico  |

### Escala Alternativa (Hipercápnica)

Utilizar somente quando houver insuficiência respiratória hipercápnica confirmada e decisão de profissional competente registrada no prontuário. Diagnóstico de DPOC isolado não autoriza automaticamente essa escala.

### Campos Adicionais Obrigatórios

| Campo              | Tipo     | Valores Possíveis             |
| ------------------ | -------- | ----------------------------- |
| Em uso de oxigênio | booleano | Sim / Não                     |
| Fluxo de oxigênio  | numérico | ex: 3 L/min                   |
| Dispositivo        | texto    | Cateter nasal, máscara, etc.  |
| Meta prescrita     | faixa    | ex: 88–92%                    |
| Escala utilizada   | enum     | Padrão / Hipercápnica         |

---

## 3. Frequência Cardíaca

**Unidade:** bpm (batimentos por minuto)  
**Referência:** adulto em repouso, faixa normal 60–100 bpm

### Tabela de Classificação

| Classificação     | Faixa   | Risco    |
| ----------------- | ------: | -------- |
| Bradicardia grave | ≤ 40    | Crítico  |
| Bradicardia       | 41–50   | Alto     |
| Limítrofe baixa   | 51–59   | Moderado |
| Normal            | 60–100  | Baixo    |
| Taquicardia leve  | 101–110 | Moderado |
| Taquicardia       | 111–130 | Alto     |
| Taquicardia grave | ≥ 131   | Crítico  |

### Observações

- As faixas são referências preliminares de triagem. Quando NEWS2 for utilizado, sua pontuação oficial deve ser calculada separadamente e identificada pela versão do protocolo.

---

## 4. Frequência Respiratória

**Unidade:** irpm (incursões respiratórias por minuto)  
**Referência:** adulto em repouso, faixa normal 12–20 irpm

### Tabela de Classificação

| Classificação    | Faixa | Risco   |
| ---------------- | ----: | ------- |
| Bradipneia grave | ≤ 8   | Crítico |
| Bradipneia       | 9–11  | Alto    |
| Normal           | 12–20 | Baixo   |
| Taquipneia       | 21–24 | Alto    |
| Taquipneia grave | ≥ 25  | Crítico |

> Estes rótulos não são uma tradução direta da pontuação NEWS2. O risco consolidado depende dos demais parâmetros e do protocolo institucional.

---

## 5. Temperatura Corporal

**Unidade:** °C  
**Referência:** média normal ~37 °C; febre ≥ 38 °C

### Tabela de Classificação

| Classificação     | Faixa     | Risco    |
| ----------------- | --------: | -------- |
| Hipotermia grave  | ≤ 35,0    | Crítico  |
| Hipotermia        | 35,1–36,0 | Alto     |
| Normal            | 36,1–37,5 | Baixo    |
| Estado febril     | 37,6–38,0 | Moderado |
| Febre             | 38,1–39,0 | Alto     |
| Febre alta        | 39,1–40,0 | Alto     |
| Hipertermia grave | > 40,0    | Crítico  |

### Campos Adicionais

| Campo            | Valores Possíveis                  |
| ---------------- | ---------------------------------- |
| Local da medição | Axilar, oral, timpânico, retal ou outro |
| Método/equipamento | Identificação do método utilizado |

> **Nota:** local e método são obrigatórios, pois valores axilares, orais, timpânicos e retais não são diretamente equivalentes. Não realizar conversões automáticas sem protocolo validado.

---

## 6. Glicemia Capilar

**Unidade:** mg/dL  
**Referência em jejum:** 70–99 mg/dL (normal)

### Tabela de Triagem para Medição em Jejum — Adulto Não Gestante

| Classificação              | Faixa   | Risco    |
| -------------------------- | ------: | -------- |
| Hipoglicemia grave         | < 54    | Crítico  |
| Hipoglicemia               | 54–69   | Alto     |
| Normal em jejum            | 70–99   | Baixo    |
| Glicemia de jejum alterada | 100–125 | Moderado |
| Valor elevado em jejum     | 126–249 | Alto     |
| Hiperglicemia importante   | 250–399 | Muito alto |
| Hiperglicemia grave        | ≥ 400   | Crítico  |

### Regras

- Valores < 70 mg/dL = hipoglicemia
- Valores < 54 mg/dL = ação imediata obrigatória
- Valores ≥ 126 mg/dL em jejum não devem ser apresentados como diagnóstico com base em uma única medição capilar.
- Faixas de jejum não se aplicam automaticamente a medições antes/depois da refeição ou aleatórias.
- Metas de pacientes diabéticos são individualizadas; gestantes e pacientes pediátricos exigem protocolos próprios e estão fora desta tabela.
- Sintomas, cetonas, estado de consciência e protocolo institucional podem elevar a prioridade.

### Contexto Obrigatório

| Campo            | Valores Possíveis                                        |
| ---------------- | -------------------------------------------------------- |
| Momento          | Jejum / Antes da refeição / Após a refeição / Aleatória |
| Tipo de paciente | Diabético / Não diabético                                |
| Uso de insulina  | Sim / Não                                                |
| Horário da última refeição | Data/hora ou desconhecido |
| Sintomas associados | Texto estruturado |

Quando o contexto obrigatório estiver ausente, classificar como **Inconclusivo**, exceto quando uma regra de segurança independente, como hipoglicemia, puder ser aplicada com o dado disponível.

---

## 7. Nível de Consciência

**Escala primária:** ACVPU (Alerta, Confusão recente, Voz, Dor, Não responde)  
**Referência:** NEWS2 — consciência e confusão recente

### Tabela de Classificação

| Classificação    | Descrição                                 | Risco   |
| ---------------- | ----------------------------------------- | ------- |
| Alerta           | Paciente consciente e orientado           | Baixo   |
| Confusão recente | Desorientação ou alteração cognitiva nova | Alto    |
| Responde à voz   | Reage quando chamado                      | Crítico |
| Responde à dor   | Reage somente a estímulo doloroso         | Crítico |
| Não responde     | Sem resposta aos estímulos                | Crítico |

### Escala de Coma de Glasgow (ECG) — Avaliação Complementar

Pontuação total: **3 (mínimo) a 15 (máximo)**

#### Abertura Ocular (O)

| Resposta             | Pontos |
| -------------------- | -----: |
| Espontânea           | 4      |
| Ao comando verbal    | 3      |
| Ao estímulo doloroso | 2      |
| Nenhuma resposta     | 1      |

#### Resposta Verbal (V)

| Resposta               | Pontos |
| ---------------------- | -----: |
| Orientado              | 5      |
| Confuso                | 4      |
| Palavras inapropriadas | 3      |
| Sons incompreensíveis  | 2      |
| Nenhuma resposta       | 1      |

#### Resposta Motora (M)

| Resposta                         | Pontos |
| -------------------------------- | -----: |
| Obedece comandos                 | 6      |
| Localiza a dor                   | 5      |
| Retirada à dor                   | 4      |
| Flexão anormal (decorticação)    | 3      |
| Extensão anormal (descerebração) | 2      |
| Nenhuma resposta                 | 1      |

#### Interpretação da Pontuação Total

| Pontuação | Classificação        | Gravidade                              |
| --------: | -------------------- | -------------------------------------- |
| 13–15     | Traumatismo leve     | —                                      |
| 9–12      | Traumatismo moderado | —                                      |
| 3–8       | Traumatismo grave    | Necessidade de proteção de vias aéreas |

#### Glasgow-P (Pupilas) — Atualização 2018

| Reatividade Pupilar    | Valor a Subtrair |
| ---------------------- | ---------------: |
| Ambas reativas         | 0                |
| Apenas uma não reativa | -1               |
| Ambas não reativas     | -2               |

> **Fórmula:** Glasgow-P = ECG − Escore Pupilar

#### Formato de Registro

```
O[1-4] V[1-5] M[1-6] = [soma] pontos
Exemplo: O4 V5 M6 = 15 pontos → consciente e orientado
Exemplo: O2 V2 M3 = 7 pontos  → rebaixamento importante
```

---

## 8. Dor

**Unidade:** escala numérica de 0 a 10  
**Instrumento:** Escala Visual Analógica (EVA) ou equivalente

### Tabela de Classificação

| Classificação    | Faixa | Risco    |
| ---------------- | ----: | -------- |
| Sem dor          | 0     | Baixo    |
| Dor leve         | 1–3   | Baixo    |
| Dor moderada     | 4–6   | Moderado |
| Dor intensa      | 7–9   | Alto     |
| Dor insuportável | 10    | Crítico  |

### Regras de Contexto

- A intensidade numérica NÃO é suficiente para classificar urgência isoladamente.
- Fatores que podem ELEVAR o risco independentemente do número:
  - Localização torácica ou abdominal
  - Início súbito
  - Sintomas associados (dispneia, sudorese, náusea)
  - Irradiação para braço, mandíbula ou dorso
- **Exemplo:** Dor torácica 5/10 com início súbito pode ser MAIS urgente que dor musculoesquelética 8/10.

---

## 9. Sintomas Relacionados à Fala

### Descrição

Os sintomas relacionados à fala e linguagem são indicadores neurológicos importantes. Podem indicar AVC, traumatismo craniano, doenças neurodegenerativas ou distúrbios metabólicos.

### Catálogo de Alterações da Fala

#### Distúrbios de Articulação e Produção

| Sintoma         | Descrição                                                      | Possíveis Causas                  |
| --------------- | -------------------------------------------------------------- | --------------------------------- |
| Disartria       | Fala arrastada, lenta ou incompreensível por fraqueza muscular | AVC, Parkinson, ELA, intoxicações |
| Apraxia da fala | Dificuldade em planejar os movimentos para produzir fala       | AVC, doenças neurodegenerativas   |
| Hipofonia       | Diminuição do volume da voz                                    | Parkinson                         |
| Disfonia        | Alteração na qualidade da voz (rouquidão, voz soprosa)         | Lesões laríngeas, neurológicas    |

#### Distúrbios de Linguagem (Afasias)

| Sintoma                          | Descrição                                                     | Possíveis Causas            |
| -------------------------------- | ------------------------------------------------------------- | --------------------------- |
| Afasia de expressão (Broca)      | Compreende, mas tem dificuldade para formar palavras e frases | AVC no hemisfério dominante |
| Afasia de compreensão (Wernicke) | Fala fluente mas sem sentido; dificuldade de compreensão      | AVC, lesões temporais       |
| Afasia global                    | Comprometimento grave da compreensão e da expressão           | AVC extenso                 |
| Anomia                           | Dificuldade em encontrar palavras ou nomear objetos           | Demências, AVC              |

#### Distúrbios de Fluência e Ritmo

| Sintoma             | Descrição                                           | Possíveis Causas                            |
| ------------------- | --------------------------------------------------- | ------------------------------------------- |
| Bradifemia          | Lentidão anormal da fala                            | Parkinson, depressão, encefalopatias        |
| Taquilalia          | Fala excessivamente rápida e difícil de compreender | Ansiedade, mania                            |
| Logorreia           | Fala excessiva e acelerada                          | Episódios maníacos, lesões neurológicas     |
| Gagueira (Disfemia) | Interrupções involuntárias na fluência da fala      | Distúrbios do desenvolvimento, neurológicos |

#### Distúrbios de Repetição e Comportamento Verbal

| Sintoma   | Descrição                                                | Possíveis Causas                              |
| --------- | -------------------------------------------------------- | --------------------------------------------- |
| Palilalia | Repetição involuntária de palavras ou frases próprias    | Parkinson, síndromes extrapiramidais          |
| Ecolalia  | Repetição automática das palavras ditas por outra pessoa | Autismo, demências, transtornos neurológicos  |
| Mutismo   | Ausência total ou quase total da fala                    | Lesões neurológicas, transtornos psiquiátricos |

#### Distúrbios de Prosódia

| Sintoma   | Descrição                            | Possíveis Causas             |
| --------- | ------------------------------------ | ---------------------------- |
| Aprosódia | Perda da entonação emocional da fala | Lesões do hemisfério direito |

### Sintomas Observacionais para Registro

- Fala clara e coerente
- Fala arrastada
- Fala lenta
- Fala acelerada
- Fala incoerente
- Dificuldade para articular palavras
- Dificuldade para encontrar palavras
- Dificuldade para compreender comandos
- Respostas monossilábicas
- Ausência de fala
- Repetição involuntária de palavras
- Voz fraca
- Rouquidão
- **Alteração súbita da fala** (sinal importante de AVC — prioridade máxima)

### Tabela de Classificação de Risco

| Classificação                        | Risco    |
| ------------------------------------ | -------- |
| Normal (fala clara e coerente)       | Baixo    |
| Alteração leve                       | Leve     |
| Alteração súbita ou grave            | Alto     |
| Afasia global / perda súbita da fala | Crítico  |

As alterações detectadas por áudio ou texto são achados candidatos. Alteração súbita deve acionar o protocolo institucional de avaliação neurológica; o modelo não confirma AVC, afasia ou outra etiologia. Idioma, sotaque, ruído, condição basal e qualidade da gravação devem ser considerados.

---

## 10. Sintomas Relacionados ao Movimento

### Descrição

Classificações para análise de vídeos de cirurgias ou sessões de fisioterapia, visando identificar padrões anômalos de movimento.

As categorias dependem de uma linha de base, do exercício/procedimento esperado, da região corporal e de limites aprovados pelo especialista. Sem esse contexto, o resultado é **Inconclusivo**. OpenPose/YOLO fornecem medidas e detecções; não diagnosticam dor, déficit neurológico ou lesão.

### 10.1 Movimentação do Paciente

| Classificação          | Descrição                                         | Risco    |
| ---------------------- | ------------------------------------------------- | -------- |
| Movimento normal       | Movimentos dentro do esperado para o procedimento | Baixo    |
| Movimento reduzido     | Amplitude menor que o esperado                    | Moderado |
| Movimento excessivo    | Agitação ou compensações                          | Moderado |
| Movimento involuntário | Tremores, espasmos ou contrações                  | Alto     |
| Ausência de movimento  | Imobilidade inesperada                            | Crítico  |

**Métricas possíveis:**

| Métrica                 | Descrição                            |
| ----------------------- | ------------------------------------ |
| Amplitude de movimento  | ROM (Range of Motion) em graus       |
| Velocidade              | Velocidade angular/linear do membro  |
| Simetria corporal       | Comparação bilateral                 |
| Frequência de movimentos | Repetições por unidade de tempo     |

### 10.2 Posição e Postura Corporal

| Classificação         | Descrição                 | Risco    |
| --------------------- | ------------------------- | -------- |
| Postura adequada      | Alinhamento esperado      | Baixo    |
| Desalinhamento leve   | Pequenas compensações     | Moderado |
| Desalinhamento severo | Pode indicar dor ou lesão | Alto     |
| Queda ou colapso      | Evento crítico            | Crítico  |

**Exemplos de observação:**

- Inclinação excessiva do tronco
- Rotação inadequada de membros
- Perda de equilíbrio

### 10.3 Padrões de Marcha (Fisioterapia)

| Classificação     | Descrição            | Risco    |
| ----------------- | -------------------- | -------- |
| Marcha normal     | Sem alterações       | Baixo    |
| Claudicação       | Assimetria na marcha | Moderado |
| Arrasto de membro | Déficit motor        | Alto     |
| Instabilidade     | Alto risco de queda  | Alto     |
| Queda             | Evento crítico       | Crítico  |

---

## 11. Análise Relacionada a Cirurgias

### Descrição

Classificações para análise multimodal (vídeo) de procedimentos cirúrgicos, identificando anomalias em ferramentas, fluxo, equipe e eventos adversos.

Este módulo é experimental no MVP. Cada especialidade e procedimento requer protocolo, fases, instrumentos esperados, limites temporais e validação próprios. Achados devem ser apresentados como “possível desvio” até confirmação da equipe. O sistema não deve usar análise de comportamento da equipe para atribuir culpa ou concluir erro médico.

### 11.1 Ferramentas Cirúrgicas

| Classificação          | Descrição                | Risco    |
| ---------------------- | ------------------------ | -------- |
| Uso correto            | Sequência esperada       | Baixo    |
| Instrumento ausente    | Falha operacional        | Moderado |
| Instrumento incorreto  | Possível erro médico     | Alto     |
| Tempo excessivo de uso | Pode indicar complicação | Alto     |

**Métricas:**

| Métrica                      | Descrição                          |
| ---------------------------- | ---------------------------------- |
| Tempo de permanência         | Duração do uso do instrumento      |
| Sequência de instrumentos    | Ordem de utilização vs. protocolo  |
| Frequência de troca          | Número de trocas por etapa         |

### 11.2 Fluxo Procedimental

| Classificação          | Descrição                        | Risco    |
| ---------------------- | -------------------------------- | -------- |
| Fluxo normal           | Procedimento dentro do protocolo | Baixo    |
| Etapa prolongada       | Possível dificuldade             | Moderado |
| Sequência anômala      | Desvio de protocolo              | Alto     |
| Interrupção inesperada | Complicação potencial            | Crítico  |

### 11.3 Equipe Cirúrgica

| Classificação           | Descrição                   | Risco    |
| ----------------------- | --------------------------- | -------- |
| Coordenação adequada    | Procedimento normal         | Baixo    |
| Aglomeração excessiva   | Pode indicar intercorrência | Moderado |
| Movimentação acelerada  | Possível emergência         | Alto     |
| Saída abrupta da equipe | Evento crítico              | Crítico  |

### 11.4 Eventos Adversos

| Evento                        | Risco   |
| ----------------------------- | ------- |
| Queda do paciente             | Crítico |
| Convulsão                     | Crítico |
| Sangramento excessivo visível | Crítico |
| Perda de consciência          | Crítico |
| Falha de equipamento          | Alto    |
| Desconexão de dispositivos    | Alto    |

“Sangramento excessivo”, “falha” e “desconexão” deverão possuir critérios observáveis e mensuráveis por procedimento. Sem limiar validado, o modelo somente sinaliza evento candidato e trecho de vídeo para revisão.

### 11.5 Análise Temporal

| Métrica                     | Indicador de Anomalia      |
| --------------------------- | -------------------------- |
| Tempo total do procedimento | Acima do esperado          |
| Tempo por etapa             | Muito longo ou muito curto |
| Tempo de recuperação        | Atrasado                   |
| Frequência de pausas        | Excessiva                  |

### 11.6 Análise Facial (quando permitido)

| Classificação    | Possível Indicação       |
| ---------------- | ------------------------ |
| Expressão de dor | Dor intensa              |
| Sonolência       | Sedação excessiva        |
| Confusão         | Alteração neurológica    |
| Estresse         | Desconforto ou ansiedade |

Expressões faciais isoladas não comprovam dor, sedação, confusão ou estresse. Esta análise exige finalidade, base legal, avaliação de viés, qualidade mínima e confirmação humana; identificação biométrica está fora do escopo.

---

## 12. Índice de Massa Corporal (IMC)

**Fórmula:** IMC = Peso (kg) ÷ Altura² (m)  
**Referência:** Classificação da OMS para adultos

### Tabela de Classificação

| Classificação                          | IMC (kg/m²) | Categoria de atenção crônica |
| -------------------------------------- | ----------: | ----------------- |
| Baixo peso grave                       | < 16,0      | Prioritária |
| Baixo peso moderado                    | 16,0–16,9   | Elevada |
| Baixo peso leve                        | 17,0–18,4   | Acompanhamento |
| Peso normal (Eutrofia)                 | 18,5–24,9   | Rotina |
| Sobrepeso                              | 25,0–29,9   | Acompanhamento |
| Obesidade Grau I                       | 30,0–34,9   | Elevada |
| Obesidade Grau II                      | 35,0–39,9   | Prioritária |
| Obesidade Grau III                     | ≥ 40,0      | Prioritária |

O IMC é indicador antropométrico e não define criticidade aguda isoladamente. A interpretação é válida para adultos e deve considerar composição corporal, contexto e protocolo clínico. Não aplicar esta tabela a crianças ou gestantes.

---

## 13. Pontuação NEWS2

Quando habilitada, a pontuação NEWS2 deve ser implementada como protocolo independente, utilizando tabelas oficiais e considerando conjuntamente frequência respiratória, SpO₂, uso de oxigênio, pressão sistólica, frequência cardíaca, temperatura e ACVPU.

- Registrar versão e escala de SpO₂ utilizada.
- Escala 2 somente por decisão clínica documentada para insuficiência respiratória hipercápnica confirmada.
- Não converter cada parâmetro isolado diretamente nos seis níveis globais.
- Exibir pontuação por parâmetro, total, gatilhos e protocolo de escalonamento institucional.
- Não calcular o total se campos obrigatórios estiverem ausentes; apresentar resultado parcial como inconclusivo.

## 14. Governança das Regras Clínicas

Cada regra publicada deve possuir:

| Metadado | Descrição |
| --- | --- |
| Identificador e versão | Referência imutável da regra |
| Fonte | Diretriz, protocolo ou literatura que a sustenta |
| População e contexto | Adulto, repouso, ambiente e condições de aplicação |
| Exclusões | Situações em que a regra não deve ser utilizada |
| Entradas obrigatórias | Campos, unidades e qualidade mínima |
| Saída e conduta | Classificação e fluxo institucional associado |
| Responsável clínico | Autor e aprovador habilitados |
| Vigência | Datas de início, revisão e retirada |
| Evidência de validação | Casos-limite, conflitos e resultados esperados |

Mudanças não sobrescrevem versões usadas em análises anteriores. O LLM pode explicar uma regra, mas não criá-la, alterar seu nível ou substituir sua execução determinística.

## 15. Regras de Qualidade e Segurança

- Preservar o valor original e registrar qualquer normalização de unidade.
- Rejeitar valores impossíveis ou unidades incompatíveis; não corrigi-los silenciosamente.
- Tratar exatamente os limites inferiores e superiores em testes automatizados.
- Registrar dados ausentes separadamente de valores normais.
- Exibir confiança de modelo separadamente do nível clínico.
- Não usar “acurácia” para uma inferência individual.
- Não inferir causalidade a partir de correlação multimodal.
- Aplicar revisão humana antes de tornar o relatório definitivo.

## 16. Referências Iniciais e Validação

- Royal College of Physicians — NEWS2: <https://www.rcplondon.ac.uk/projects/outputs/national-early-warning-score-news-2>
- Organização Mundial da Saúde — referências de antropometria e IMC: <https://www.who.int/data/gho/data/themes/topics/topic-details/GHO/body-mass-index>
- Sociedade Brasileira de Diabetes — diretrizes vigentes: <https://diretriz.diabetes.org.br/>
- Diretrizes brasileiras e protocolos institucionais vigentes para pressão arterial, glicemia, deterioração clínica e resposta a emergências.

A presença de uma referência nesta seção não significa que todas as faixas do documento já foram validadas contra sua edição mais recente. Antes de transformar uma tabela em regra ativa, o responsável clínico deverá registrar a fonte exata, edição, página, população, adaptações locais e evidência de validação.

---
