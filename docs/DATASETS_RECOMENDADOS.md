# Datasets recomendados — Áudio, Vídeo e Imagem

Este documento organiza fontes de datasets públicos para testar o
sistema com dados reais, cobrindo as três modalidades de mídia exigidas
no Tech Challenge (áudio, vídeo, imagem). Inclui os dois datasets
sugeridos no documento do desafio (PhysioNet e Google AudioSet) e
alternativas mais específicas para o caso de uso clínico do
SentinelHealth (voz com fadiga/disartria, vídeo de fisioterapia/cirurgia
com pose e detecção de objetos, imagem clínica/radiológica).

> Nenhum destes datasets está integrado ao código — o projeto usa dados
> sintéticos próprios (`make seed-patients` etc.). Baixar amostras
> pequenas (1-2 arquivos) já é suficiente para alimentar o fluxo de
> upload manualmente durante os testes/demonstração.

---

## Portais gerais (ponto de partida para buscar mais opções)

| Site | O que encontrar | Link |
| --- | --- | --- |
| PhysioNet | Sinais fisiológicos, voz patológica, sinais vitais de UTI — sugerido no PDF | <https://physionet.org/> |
| Google AudioSet | Clipes de áudio do YouTube rotulados por categoria de som — sugerido no PDF | <https://research.google.com/audioset/> |
| Kaggle Datasets | Busca por palavra-chave, inclui datasets de áudio/vídeo/imagem médica | <https://www.kaggle.com/datasets> |
| Hugging Face Datasets | Datasets de áudio/vídeo/imagem, muitos já prontos para download via `datasets` (Python) | <https://huggingface.co/datasets> |
| Papers with Code — Datasets | Datasets vinculados a papers, filtráveis por tarefa (pose estimation, ASR, etc.) | <https://paperswithcode.com/datasets> |
| Awesome Medical Dataset (GitHub) | Lista curada de datasets médicos (imagem, vídeo cirúrgico, sinais) | <https://github.com/openmedlab/Awesome-Medical-Dataset> |
| Grand Challenge | Datasets e benchmarks de imagem/vídeo médico organizados por desafio científico | <https://grand-challenge.org/> |
| Zenodo | Repositório genérico de dados de pesquisa, inclui muitos datasets de saúde com DOI | <https://zenodo.org/> |

---

## Áudio (voz, fala, alterações vocais)

| Dataset | Conteúdo | Onde encontrar |
| --- | --- | --- |
| **Google AudioSet** (sugerido no PDF) | 2M+ clipes de 10s do YouTube, 527 categorias de som, incluindo voz humana e fala | <https://research.google.com/audioset/dataset/index.html> |
| **PhysioNet — Voice ICar fEDerico II** (sugerido no PDF, categoria voz) | Voz de pacientes com patologias laríngeas (disfonia, laringite por refluxo) vs. controles saudáveis | <https://physionet.org/> (buscar "Voice ICar fEDerico") |
| **EasyCall Corpus** | 21.386 gravações, 24 falantes saudáveis + 31 disártricos, severidade avaliada por neurologistas | <https://www.researchgate.net/publication/354221057_EasyCall_Corpus_A_Dysarthric_Speech_Dataset> |
| **Voice signals database of ALS patients** (Nature Sci Data) | 1.224 sinais de voz, 153 participantes (102 com ELA/disartria) | <https://www.nature.com/articles/s41597-024-03597-2> |
| **HeyJay! corpus** | Fala atípica (disartria, disfonia) multilíngue | <https://www.nature.com/articles/s41597-026-07497-5> |
| **Mozilla Common Voice** | Fala geral multilíngue (inclui pt-BR), útil para testar transcrição/ASR fora do contexto clínico | <https://commonvoice.mozilla.org/> |

---

## Vídeo (postura, cirurgia, fisioterapia)

| Dataset | Conteúdo | Onde encontrar |
| --- | --- | --- |
| **UCO Physical Rehabilitation** | Vídeos de exercícios de fisioterapia com avaliação de métodos de pose (OpenPose entre eles) | <https://pmc.ncbi.nlm.nih.gov/articles/PMC10648737/> |
| **REHAB24-6** | Vídeos RGB não cortados + esqueleto 2D/3D + segmentação temporal de 6 exercícios de reabilitação | Buscar "REHAB24-6" no Papers with Code ou Springer |
| **KERAAL / Low-Back Pain Rehab Dataset** | Kinect 3D skeleton + RGB + anotações médicas de erro de movimento | <https://arxiv.org/html/2407.00521> |
| **Cholec80** | 80 vídeos de colecistectomia laparoscópica, anotados com fases cirúrgicas + presença de instrumentos | <https://github.com/openmedlab/Awesome-Medical-Dataset/blob/main/resources/Cholec80.md> |
| **Endoscapes2023** | 201 vídeos de colecistectomia laparoscópica com segmentação de instrumentos/anatomia + avaliação de segurança por cirurgiões | <https://www.nature.com/articles/s41597-025-04642-4> |
| **SurgeNetYoutube** | 680h de vídeo cirúrgico extraído do YouTube, 1 fps, sem anotação clínica formal | <https://huggingface.co/datasets/TimJaspersTue/SurgeNetYoutube> |
| **Grand Challenge (cirurgia/pose)** | Vários datasets de vídeo cirúrgico/movimento organizados por desafio | <https://grand-challenge.org/> |

---

## Imagem (clínica, radiológica, dermatológica)

| Dataset | Conteúdo | Onde encontrar |
| --- | --- | --- |
| **NIH Chest X-ray** | 100.000 radiografias de tórax desidentificadas, formato PNG | <https://docs.cloud.google.com/healthcare-api/docs/resources/public-datasets/nih-chest> |
| **VinDr-CXR** | 18.000 raios-X de tórax anotados por 17 radiologistas, bounding boxes de anormalidades | <https://pmc.ncbi.nlm.nih.gov/articles/PMC9300612/> |
| **MIMIC-CXR** | Radiografias de tórax desidentificadas + laudos em texto livre (exige credenciamento PhysioNet) | <https://physionet.org/> (buscar "MIMIC-CXR") |
| **PadChest** | 160.000+ imagens de raio-X + relatórios multi-rótulo (em espanhol) | <http://bimcv.cipf.es/bimcv-projects/padchest/> |
| **SkinDisNet** | Imagens clínicas + metadados para doenças de pele | <https://pmc.ncbi.nlm.nih.gov/articles/PMC12664407/> |
| **ISIC Archive** | Imagens dermatoscópicas de lesões de pele, com anotação de diagnóstico | <https://www.isic-archive.com/> |

---

## Sinais vitais / séries temporais (para a detecção de anomalias)

| Dataset | Conteúdo | Onde encontrar |
| --- | --- | --- |
| **PhysioNet MIMIC Database** (sugerido no PDF) | Sinais vitais contínuos de UTI (FC, PA, FR, SpO2), ~90+ pacientes, ~200 dias-paciente | <https://physionet.org/content/mimicdb/> |
| **MIMIC-III-Ext-PPG** | FC, FR, PA sistólica/diastólica já extraídas de sinais PPG/ABP/ECG (menos pré-processamento) | <https://www.nature.com/articles/s41597-026-07335-8> |

---

## Observações práticas

1. **Acesso restrito**: vários datasets de saúde (MIMIC-III completo, MIMIC-CXR) exigem
   credenciamento no PhysioNet (treinamento de ética + assinatura de *data use agreement*)
   antes do download. Para uma demonstração pontual, isso costuma ser desproporcional —
   prefira datasets sem barreira de acesso (AudioSet, Cholec80, NIH Chest X-ray, ISIC Archive,
   EasyCall Corpus) quando o objetivo for só validar o fluxo de upload/processamento.
2. **Tamanho de amostra**: baixe 1-2 arquivos pequenos (um WAV curto, um MP4 curto, uma
   imagem PNG/JPEG) em vez do dataset inteiro — é o suficiente para exercitar o pipeline
   de análise multimodal ponta a ponta.
3. **Dados sintéticos vs. reais**: o `ESCOPO_PROJETO.md` (seção 8.2) exige dados sintéticos
   fora de produção. Usar um dataset público de pesquisa (já anonimizado/desidentificado
   pelos autores) para teste é aceitável, mas nunca substitua isso por dado real de paciente
   próprio sem passar pelo gate de aprovação descrito no escopo.
