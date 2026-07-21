"""Gera o diagrama de arquitetura do ambiente LOCAL/DEV do SentinelHealth
(o que roda hoje na maquina do desenvolvedor), para apresentar ANTES da
visao de producao (`build_diagram.py`) ao comite de arquitetura.

Fonte de verdade: `compose.yaml` (modo 100% local), `compose.aws-dev.yaml`
(override opcional que conecta os MESMOS containers a servicos AWS reais),
`infra/environments/dev/` (S3+SQS+KMS minimos provisionados via Terraform
para esse modo) e `infra/iam-policies/sentinelhealth-dev-local-aws-policy.json`.

Mostra os DOIS submodos que coexistem hoje, ativados pela mesma base de
codigo/containers, apenas trocando variaveis de ambiente + credenciais:

1. Modo 100% LOCAL (`docker compose -f compose.yaml up`): adaptadores
   LOCAL para storage/fila/LLM/transcricao/visao - nenhuma chamada de
   rede externa, tudo dentro do Docker Compose na maquina do dev.
2. Modo DEV-AWS (`docker compose -f compose.yaml -f compose.aws-dev.yaml
   up`): os MESMOS containers (nenhuma imagem diferente), mas com
   MEDIA_STORAGE_BACKEND=S3/TRANSCRIPTION_PROVIDER=AWS_TRANSCRIBE/feature
   flags de Rekognition ligadas - conectando a um bucket S3, fila SQS e
   chave KMS reais (conta AWS 479844459009, ambiente "dev" minimo, SEM
   VPC/RDS/ECS - ver infra/environments/dev/README.md), usando uma copia
   ISOLADA e read-only das credenciais do desenvolvedor
   (~/.aws-sentinelhealth-dev, NUNCA o ~/.aws completo).

Uso:
    python3 -m venv .venv && source .venv/bin/activate
    pip install diagrams
    brew install graphviz   # (ou apt-get install graphviz)
    python3 docs/architecture/scripts/build_diagram_local_dev.py
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.integration import SQS
from diagrams.aws.ml import Rekognition, Transcribe
from diagrams.aws.security import KMS
from diagrams.aws.storage import S3
from diagrams.generic.network import Firewall
from diagrams.onprem.client import Users
from diagrams.onprem.container import Docker
from diagrams.onprem.database import PostgreSQL
from diagrams.programming.framework import React
from diagrams.programming.language import Python

GRAPH_ATTR = {
    "fontsize": "22",
    "fontname": "Helvetica-Bold",
    "bgcolor": "white",
    "pad": "0.6",
    "nodesep": "0.6",
    "ranksep": "0.9",
    "splines": "spline",
    "labelloc": "t",
}
NODE_ATTR = {"fontname": "Helvetica", "fontsize": "12"}
EDGE_ATTR = {"fontname": "Helvetica", "fontsize": "10"}

with Diagram(
    "SentinelHealth \u2014 Ambiente Local / Dev (antes da AWS de producao)",
    filename="sentinelhealth_architecture_local_dev",
    show=False,
    direction="TB",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
    outformat=["png", "svg", "pdf"],
):
    dev = Users("Desenvolvedor\n(maquina local)")

    with Cluster("Terceiro externo (mesmo em dev, se OPENAI_API_KEY setado)"):
        openai = React("OpenAI API\n(LLM_PROVIDER=OPENAI)")

    with Cluster("Docker Compose \u2014 docker compose -f compose.yaml up"):
        frontend = Docker("frontend\nnginx :5173\u219280\nbuild estatico Vite/React")
        backend = Python("backend\nFastAPI/uvicorn :8000\n(mesma imagem serve API +\nworker via scripts/*.py)")
        postgres = PostgreSQL("postgres:16-alpine :5432\nfonte de verdade\n(volume nomeado)")

        frontend >> Edge(label="HTTP") >> backend
        backend >> Edge(label="SQL") >> postgres

        with Cluster("Modo 1: 100% LOCAL (padrao, sem AWS)"):
            local_storage = Docker("Adaptador de storage LOCAL\nfilesystem em .local-media/\n(quarantine/ \u2192 approved/)")
            local_queue = Docker("Fila LOCAL\ntabela Postgres\n(SELECT...FOR UPDATE SKIP LOCKED)")
            local_llm = Docker("LLM LOCAL\ntemplate deterministico\n(sem chamada de rede)")
            local_asr = Docker("Transcricao/Visao LOCAL\nretorna UNAVAILABLE honesto\n(nunca fabrica resultado)")

            backend >> Edge(style="dashed", color="gray", label="MEDIA_STORAGE_BACKEND=LOCAL") >> local_storage
            backend >> Edge(style="dashed", color="gray") >> local_queue
            backend >> Edge(style="dashed", color="gray", label="flags desligadas (default)") >> local_llm
            backend >> Edge(style="dashed", color="gray") >> local_asr

    with Cluster(
        "Modo 2: DEV conectado a AWS real\n"
        "(override opcional: docker compose -f compose.yaml -f compose.aws-dev.yaml up)"
    ):
        aws_creds = Firewall(
            "~/.aws-sentinelhealth-dev\n(credenciais ISOLADAS, :ro)\nNUNCA o ~/.aws completo"
        )

        with Cluster("Conta AWS 479844459009 \u2014 ambiente \"dev\" (sem VPC/RDS/ECS)"):
            kms = KMS("KMS\nalias/sentinelhealth-dev")
            s3_dev = S3("S3\nsentinelhealth-dev-media\nquarantine/\u2192approved/\u2192transcriptions/")
            sqs_dev = SQS("SQS\nsentinelhealth-dev-analysis-queue\n+ DLQ")
            transcribe_dev = Transcribe("Amazon Transcribe\n(batch, pt-BR)")
            rekognition_dev = Rekognition(
                "Amazon Rekognition\nImage + Video\n(feature flags,\nopcional/complementar)"
            )

        backend >> Edge(
            style="bold",
            color="#d35400",
            label="boto3 (credenciais isoladas)\nMEDIA_STORAGE_BACKEND=S3",
        ) >> aws_creds
        aws_creds >> Edge(color="#d35400") >> s3_dev
        aws_creds >> Edge(color="#d35400") >> sqs_dev
        aws_creds >> Edge(color="#d35400", label="TRANSCRIPTION_PROVIDER=\nAWS_TRANSCRIBE") >> transcribe_dev
        aws_creds >> Edge(
            color="#d35400", style="dashed", label="feature flags\nimage/video_recognition_enabled"
        ) >> rekognition_dev
        transcribe_dev >> Edge(style="dashed", color="gray", label="le/grava resultado") >> s3_dev

        for res in (s3_dev, sqs_dev):
            kms >> Edge(color="lightgray", style="dotted") >> res

    backend >> Edge(
        style="dashed", color="gray", label="LLM_PROVIDER=OPENAI\n(flag opcional, ambos os modos)"
    ) >> openai

    dev >> Edge(label="http://localhost:5173") >> frontend
    dev >> Edge(label="http://localhost:8000\n(X-Dev-Subject, sem MFA)", style="dashed") >> backend
