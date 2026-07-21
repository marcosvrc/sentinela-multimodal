"""Adaptador de fila Amazon SQS (homologacao/producao).

Nao exercitado pelos testes deste sandbox (sem credenciais/conta AWS); os
testes de integracao reais rodam separadamente contra uma conta AWS de
desenvolvimento quando credenciais estiverem disponiveis.
"""

from __future__ import annotations

import json

import boto3

from app.queue.base import QueueMessage


class SqsQueueAdapter:
    def __init__(self, *, queue_url: str, region: str):
        self._queue_url = queue_url
        self._client = boto3.client("sqs", region_name=region)

    def enqueue(self, body: dict) -> None:
        self._client.send_message(QueueUrl=self._queue_url, MessageBody=json.dumps(body))

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        response = self._client.receive_message(
            QueueUrl=self._queue_url, MaxNumberOfMessages=max_messages
        )
        return [
            QueueMessage(receipt_handle=message["ReceiptHandle"], body=json.loads(message["Body"]))
            for message in response.get("Messages", [])
        ]

    def delete(self, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
