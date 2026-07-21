# ADR 0016: Avaliacao de componentes AWS gerenciados para audio, video e imagem

**Status:** Superado (ver nota abaixo)
**Data:** 2026-07-11

> **Atualizacao (2026-07-21):** o projeto passou a usar exclusivamente
> Azure como nuvem gerenciada, removendo toda a infraestrutura e
> adaptadores AWS (Rekognition Image/Video, Transcribe, Comprehend). Os
> adaptadores reais hoje sao Azure AI Speech (audio), Azure AI Language
> (sentimento/termos) e Azure AI Vision (imagem, enriquecimento opcional).
> A conclusao sobre video (worker self-hosted OpenPose/YOLOv8, pois
> nenhum servico gerenciado de visao oferece estimativa de pose) permanece
> valida e inalterada. Registro historico da avaliacao original.

## Contexto

Antes de implementar o item 4.1 (analise de video), foi solicitada uma
avaliacao explicita do uso de servicos gerenciados da AWS (Amazon
Rekognition, Amazon Textract, Amazon Transcribe/Transcribe Medical) para as
tres modalidades de midia do escopo (audio, video, imagem), comparando com
as escolhas ja definidas no `ESCOPO_PROJETO.md` (secoes 4.1, 6.2, 6.3, 12.4)
e com o que ja foi implementado nos itens 4.2 (audio) e 4.4 (imagem).

Pesquisa realizada em 2026-07-11 (precos e disponibilidade sujeitos a
mudanca; ver fontes ao final).

## Servicos avaliados

### Amazon Transcribe (padrao) — ja adotado no item 4.2

O escopo (secao 6.2/6.3) ja especifica Amazon Transcribe padrao, batch,
`pt-BR`, e e exatamente o que o adaptador `AwsTranscribeAdapter` (item 4.2)
implementa. A pesquisa confirma que essa e a escolha correta:

- Preco de tier 1: ~US$ 0,024/minuto (batch), sem taxa adicional so por usar
  batch em vez de streaming.
- **Amazon Transcribe Medical foi avaliado e descartado**: custa ~US$
  0,075/minuto (3x mais caro) e, mais importante, **so suporta ingles dos
  EUA (`en-US`)** — nao ha suporte a `pt-BR`. Como a cadeia principal do
  projeto opera em portugues brasileiro (confirmado na secao 6.3 do
  escopo), Transcribe Medical e inviavel independentemente do custo.

**Conclusao:** manter Amazon Transcribe padrao `pt-BR` batch, como ja
implementado. Nenhuma mudanca no item 4.2.

### Amazon Textract — candidato para imagem (item 4.4, categoria `SCANNED_DOCUMENT`)

O item 4.4 hoje classifica imagens em categorias (`SCANNED_DOCUMENT`,
`CLINICAL_IMAGE`, `GENERIC_PHOTO`) por heuristica de pixel
(`app/vision/image_category.py`), sem extrair o conteudo textual do
documento.

- Textract e desenhado especificamente para documentos (formularios,
  tabelas, paginas de texto), diferente do Rekognition `DetectText` (que e
  para texto em cena, como placas e rotulos).
- Preco: ~US$ 1,50 por 1.000 paginas so para deteccao de texto
  (`DetectDocumentText`); recursos adicionais (formularios ~US$ 50/1.000
  paginas, tabelas ~US$ 15/1.000 paginas) sao caros e nao necessarios para
  o MVP.
- **Nao esta no escopo do MVP**: o escopo nao pede extracao de texto de
  documentos escaneados como entrega obrigatoria da secao 4 — apenas
  categorizacao da imagem. Adicionar OCR real seria um servico gerenciado
  novo, fora do que foi definido nas secoes 4.4/6.2, com implicacoes de
  custo, IAM e tratamento de dados (o texto de um documento medico
  escaneado pode conter dados de saude identificaveis, exigindo os mesmos
  cuidados de minimizacao ja aplicados ao LLM).

**Conclusao:** nao adotar Textract neste momento. Registrar como evolucao
futura (nao obrigatoria) caso o produto passe a exigir OCR real de
documentos escaneados — nesse caso, o padrao de adaptador (`Protocol` +
factory por `Settings`) ja usado em `storage`, `llm` e `transcription`
seria reaplicado para isolar o SDK do dominio.

### Amazon Rekognition (Image e Video) — candidato para imagem (4.4) e video (4.1)

- **Rekognition Image** (`DetectLabels`, `DetectModerationLabels`, etc.):
  preco ~US$ 0,001/imagem. Poderia enriquecer a categorizacao heuristica de
  imagem do item 4.4 com rotulos genericos (ex.: "X-Ray", "Person",
  "Document"), mas **nao substitui** a analise de area de interesse ja
  implementada (heuristica de densidade de borda por quadrante), que e
  descritiva de textura/composicao, nao de objetos.
- **Rekognition Video**: preco ~US$ 0,10/minuto (deteccao de rotulo/pessoa);
  free tier de 60 min/mes no primeiro ano.
- **Ponto decisivo para o item 4.1: Rekognition nao faz estimativa de pose
  (keypoints articulares)**. O escopo exige explicitamente OpenPose
  (analise postural) + YOLOv8 (deteccao de objetos/areas criticas) como os
  modelos do worker de video (secao 4.1, linha "Modelos"). Rekognition
  Video oferece deteccao de rotulo, rosto, pessoa e (historicamente)
  "People Pathing" (rastreamento de trajetoria de pessoas) — mas **nao**
  keypoints de pose articulada, que e o dado necessario para os achados de
  padrao postural anomalo pedidos no escopo.
- Adicionalmente, a pesquisa indica que a AWS esta descontinuando recursos
  de video streaming do Rekognition para novos clientes (a partir de
  30/04/2026) e ha material da propria AWS orientando migracao do "People
  Pathing" para alternativas — sinal de que a superficie de recursos de
  video do Rekognition esta em contracao, nao expansao, reduzindo a
  atratividade de depender dele para uma capacidade central do MVP.
- Deteccao de objetos genericos (YOLO-like) via Rekognition Custom Labels
  exigiria treinar um modelo customizado com dataset proprio (nao e
  zero-shot como o YOLOv8 pre-treinado), o que nao reduz esforco de forma
  relevante frente ao worker self-hosted ja especificado no escopo.

**Conclusao:** manter a decisao do escopo — worker de video self-hosted
(OpenPose + YOLOv8 em CPU, secoes 4.1/6.2/6.3/12.4) para o item 4.1.
Rekognition Video nao cobre o requisito central (pose estimation) e nao
ha vantagem de custo/esforco relevante para o restante. Rekognition Image
fica registrado como enriquecimento *opcional e futuro* da categorizacao
de imagem do item 4.4 (rotulos genericos complementando a heuristica
atual), nunca como substituicao.

## Decisao

1. **Audio (4.2):** manter Amazon Transcribe padrao `pt-BR` batch — ja
   implementado, confirmado como a escolha correta. Transcribe Medical
   descartado (sem suporte a `pt-BR`).
2. **Imagem (4.4):** manter a heuristica atual (categoria + area de
   interesse por pixel). Nao adotar Textract nem Rekognition Image no MVP;
   registrados como evolucoes futuras opcionais, fora do escopo obrigatorio
   da secao 4.
3. **Video (4.1):** manter a decisao do escopo — worker self-hosted
   OpenPose + YOLOv8 em CPU. Rekognition Video nao substitui a estimativa
   de pose exigida e esta com superficie de recursos em contracao.
   Implementacao do item 4.1 segue como planejado, sem uso de Rekognition.

## Alternativas consideradas

- Usar Rekognition Video como base do item 4.1 em vez de OpenPose/YOLOv8:
  rejeitado — nao oferece pose estimation (requisito central do escopo) e
  divergiria da decisao explicita do `ESCOPO_PROJETO.md`.
- Adotar Transcribe Medical no item 4.2: rejeitado — 3x mais caro e sem
  suporte a `pt-BR`.
- Adotar Textract para leitura de documentos escaneados no item 4.4:
  adiado — fora do escopo obrigatorio atual; pode ser reavaliado se o
  produto exigir OCR real de documentos no futuro.

## Consequencias

- O item 4.1 sera implementado com o worker self-hosted OpenPose + YOLOv8
  em CPU, conforme ja planejado, sem alteracao de rota por causa desta
  avaliacao.
- Nenhuma mudanca e necessaria nos itens 4.2 e 4.4 ja implementados.
- Caso o produto evolua para exigir OCR de documentos ou enriquecimento de
  rotulos de imagem, Textract e Rekognition Image ficam registrados como
  candidatos, a serem isolados via adaptador (`Protocol` + factory por
  `Settings`), no mesmo padrao ja usado para `storage`, `llm` e
  `transcription`.

## Atualizacao (2026-07-16): Rekognition Image/Video implementados como enriquecimento opcional

O "candidato futuro" registrado acima para Rekognition Image foi
implementado, e estendido tambem para Rekognition Video, SEMPRE como
enriquecimento OPCIONAL e nunca como substituicao das decisoes originais
desta ADR:

- `app.integrations.image_recognition` (Rekognition Image, `DetectLabels`,
  sincrono) - roda apos a heuristica de categoria/regiao de interesse
  existente (`app.vision.image_category`), gravando um achado
  `MODEL_OBSERVATION` SEPARADO com rotulos genericos. Feature flag
  `image_recognition_enabled` (default `False`).
- `app.integrations.video_recognition` (Rekognition Video,
  `StartLabelDetection`/`GetLabelDetection`, assincrono - mesmo padrao de
  poll sincrono do `AwsTranscribeAdapter`) - roda APOS o worker OpenPose/
  YOLOv8 (`app.integrations.vision`), gravando outro achado
  `MODEL_OBSERVATION` SEPARADO com rotulos genericos e timestamp. Feature
  flag `vision_rekognition_video_enabled` (default `False`). O worker
  self-hosted continua sendo a UNICA fonte de estimativa de pose - o
  motivo original desta ADR para rejeitar Rekognition como motor
  principal de video permanece valido e inalterado.

Nenhum recurso Terraform novo foi necessario (reaproveita o bucket
`sentinelhealth-dev-*` e o prefixo `approved/` ja usados pelo Transcribe);
apenas a permissao IAM `RekognitionRuntime` foi adicionada a
`infra/iam-policies/sentinelhealth-dev-local-aws-policy.json`. Ver
`infra/environments/dev/README.md`.

Amazon Transcribe Medical e Amazon Comprehend Medical foram avaliados para
uso complementar (analise clinica mais estruturada de sintomas/entidades
medicas) e **descartados** pelo mesmo motivo que rejeitou Transcribe
Medical na secao original desta ADR: ambos suportam exclusivamente ingles
dos EUA (`en-US`), sem nenhum suporte a `pt-BR` - confirmado na
documentacao oficial da AWS. Como toda a cadeia clinica do projeto opera
em portugues brasileiro, os dois servicos ficariam permanentemente
inutilizaveis no fluxo real e nao foram implementados. Registrados aqui
apenas para nao serem re-avaliados no futuro sem essa informacao.

## Fontes consultadas

- [Amazon Rekognition — pricing](https://aws.amazon.com/rekognition/pricing/)
- [Amazon Rekognition — Video features](https://aws.amazon.com/rekognition/video-features/)
- [Amazon Textract — pricing](https://aws.amazon.com/textract/pricing/)
- [Amazon Transcribe — pricing](https://aws.amazon.com/transcribe/pricing/)
- [Amazon Transcribe Medical](https://aws.amazon.com/transcribe/medical/)
- [Amazon Transcribe — supported languages](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html)
- [Transitioning from Amazon Rekognition people pathing: Exploring other alternatives](https://aws.amazon.com/blogs/machine-learning/transitioning-from-amazon-rekognition-people-pathing-exploring-other-alternatives/)
- [Rekognition Custom Labels vs SageMaker](https://www.rapyder.com/blog/amazon-rekognition-custom-labels-vs-sagemaker-image-classification-object-detection-algorithms/)
