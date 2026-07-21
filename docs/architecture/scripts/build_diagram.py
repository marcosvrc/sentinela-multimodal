"""Gera o diagrama de arquitetura profissional do SentinelHealth (ambiente
production/homologation na AWS) para apresentacao ao comite de arquitetura.

Fonte de verdade: infra/modules/*, infra/environments/production/*,
backend/app/integrations/*. Nao inventa nenhum componente - reflete
exatamente o que esta provisionado via Terraform + o que e chamado via
boto3/HTTP em runtime. Mantido versionado (nao apenas a imagem gerada)
para que a arquitetura possa ser regenerada quando a infraestrutura
evoluir, em vez de editar a imagem manualmente.

Uso:
    python3 -m venv .venv && source .venv/bin/activate
    pip install diagrams
    brew install graphviz   # (ou apt-get install graphviz)
    python3 docs/architecture/scripts/build_diagram.py

Gera sentinelhealth_architecture.{png,svg,pdf} no diretorio atual - mover
para docs/architecture/ depois.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR, ECS, Fargate
from diagrams.aws.database import RDS
from diagrams.aws.integration import SQS
from diagrams.aws.management import Cloudwatch
from diagrams.aws.ml import Rekognition, Transcribe
from diagrams.aws.network import ALB, InternetGateway, NATGateway
from diagrams.aws.security import KMS, Cognito, SecretsManager
from diagrams.aws.storage import S3
from diagrams.generic.network import Firewall
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Users
from diagrams.onprem.vcs import Github
from diagrams.programming.framework import React

GRAPH_ATTR = {
    "fontsize": "22",
    "fontname": "Helvetica-Bold",
    "bgcolor": "white",
    "pad": "0.6",
    "nodesep": "0.7",
    "ranksep": "0.9",
    "splines": "spline",
    "labelloc": "t",
}
NODE_ATTR = {"fontname": "Helvetica", "fontsize": "12"}
EDGE_ATTR = {"fontname": "Helvetica", "fontsize": "10"}

with Diagram(
    "SentinelHealth \u2014 Arquitetura AWS (Producao/Homologacao)",
    filename="sentinelhealth_architecture",
    show=False,
    direction="TB",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
    outformat=["png", "svg", "pdf"],
):
    users = Users("Profissionais de saude\n(medico, enfermeiro, admin)")

    with Cluster("Terceiro externo (fora da AWS)"):
        openai = React("OpenAI API\n(sintese/explicacao textual\nnunca decide risco)")

    with Cluster("CI/CD (GitHub)"):
        repo = Github("Repositorio\n(monorepo)")
        ci = GithubActions("GitHub Actions\nlint / testes / build\n(deploy manual)")
        repo >> ci

    with Cluster("AWS \u2014 Conta unica, regiao us-east-1"):
        cognito = Cognito("Amazon Cognito\nUser Pool + MFA\n(OIDC, sem self-signup)")
        kms = KMS("AWS KMS\n(CMK por ambiente)")
        secrets = SecretsManager("Secrets Manager\n(OpenAI key, credenciais DB)")
        ecr = ECR("Amazon ECR\n(repos: api, worker)")
        logs = Cloudwatch("CloudWatch Logs\n(retencao 365d prod)")

        with Cluster("VPC (3 AZs)"):
            igw = InternetGateway("Internet Gateway")

            with Cluster("Subnets publicas"):
                alb = ALB("Application\nLoad Balancer\n:443")
                nat = NATGateway("NAT Gateway\n(1 por AZ em prod)")

            with Cluster("Subnets privadas"):
                fw = Firewall("Security Groups\nALB\u2192ECS\u2192RDS\n(sem acesso publico)")

                with Cluster("ECS Fargate Cluster"):
                    api_svc = ECS("Servico API\n(FastAPI, 3 replicas)")

                    with Cluster("Workers (SQS consumers, sem ALB)"):
                        w_orch = Fargate("worker-orchestrator\n(maquina de estados)")
                        w_audio = Fargate("worker-audio\n(transcricao + NLP)")
                        w_video = Fargate("worker-video-image\n(OpenPose+YOLOv8+ffmpeg\nself-hosted, CPU maior)")
                        w_report = Fargate("worker-report\n(PDF + LLM)")

                rds = RDS("Amazon RDS PostgreSQL 16\nMulti-AZ (prod)\nfonte de verdade")

        sqs = SQS("SQS\nanalysis-queue + DLQ")
        s3 = S3("S3 \u2014 bucket de midia\nquarantine/ \u2192 approved/ \u2192 generated/\nSSE-KMS, versionado")
        transcribe = Transcribe("Amazon Transcribe\n(batch, pt-BR)")
        rekognition = Rekognition("Amazon Rekognition\nImage + Video\n(enriquecimento opcional\ncomplementar, ADR 0016)")

    # --- Fluxo do usuario ---
    users >> Edge(label="HTTPS") >> igw >> alb
    alb >> Edge(label="autentica via") >> cognito
    alb >> Edge(label=":8000") >> api_svc

    # --- API <-> dados/fila/midia ---
    api_svc >> Edge(label="SQL") >> rds
    api_svc >> Edge(label="enfileira analise") >> sqs
    api_svc >> Edge(label="URL pre-assinada\n(upload direto)") >> s3
    api_svc >> Edge(label="le/valida token") >> cognito
    api_svc >> Edge(color="gray", style="dashed", label="segredos") >> secrets

    # --- Workers consumindo a fila ---
    sqs >> Edge(label="poll") >> w_orch
    w_orch >> Edge(label="despacha por modalidade") >> w_audio
    w_orch >> w_video
    w_orch >> w_report
    w_orch >> Edge(color="gray") >> rds

    w_audio >> Edge(label="le midia aprovada") >> s3
    w_audio >> Edge(label="StartTranscriptionJob") >> transcribe
    w_audio >> Edge(color="gray") >> rds

    w_video >> Edge(label="le midia aprovada") >> s3
    w_video >> Edge(label="DetectLabels /\nStartLabelDetection\n(opcional, feature flag)", style="dashed") >> rekognition
    w_video >> Edge(color="gray") >> rds

    w_report >> Edge(label="grava PDF") >> s3
    w_report >> Edge(label="sintese textual\n(allowlist minimizada)") >> openai
    w_report >> Edge(color="gray") >> rds

    transcribe >> Edge(label="grava resultado JSON", style="dashed") >> s3

    # --- Observabilidade / seguranca (linhas leves, nao poluir o fluxo principal) ---
    api_svc >> Edge(color="lightgray", style="dotted") >> logs
    w_orch >> Edge(color="lightgray", style="dotted") >> logs

    for res in (rds, s3, sqs, secrets):
        res >> Edge(color="lightgray", style="dotted", label="") >> kms

    ecr >> Edge(color="lightgray", style="dotted", label="pull imagem") >> api_svc
    ecr >> Edge(color="lightgray", style="dotted") >> w_orch

    ci >> Edge(color="lightgray", style="dotted", label="build/push\n(manual)") >> ecr
