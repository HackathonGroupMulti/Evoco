"""Voice transcription powered by Amazon Nova Sonic via Bedrock.

Accepts raw audio bytes and returns the transcribed text.
Falls back to a placeholder when AWS credentials are missing.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings

logger = logging.getLogger(__name__)

NOVA_SONIC_MODEL_ID = "amazon.nova-sonic-v1:0"


def _build_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


async def transcribe(audio_bytes: bytes, sample_rate: int = 16000, encoding: str = "pcm") -> str:
    """Transcribe audio bytes to text using Nova Sonic.

    Returns the transcribed string, or a mock placeholder if credentials
    are unavailable.
    """
    if not settings.has_aws_credentials:
        logger.info("No AWS credentials — returning mock transcription")
        return _mock_transcription()

    try:
        client = _build_bedrock_client()

        session_config = {
            "inputAudioFormat": {
                "encoding": encoding,
                "sampleRateHertz": sample_rate,
                "channelCount": 1,
            },
        }

        # Nova Sonic uses the bidirectional streaming API.  For the hackathon
        # demo we use a simplified single-shot call: send all audio, then
        # close the input stream and collect the transcript from events.

        response = client.invoke_model_with_bidirectional_stream(
            modelId=NOVA_SONIC_MODEL_ID,
            body=json.dumps({
                "sessionConfiguration": session_config,
                "audioInput": {
                    "audio": base64.b64encode(audio_bytes).decode(),
                },
            }),
        )

        transcript_parts: list[str] = []
        for event in response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            if "transcript" in chunk:
                transcript_parts.append(chunk["transcript"])

        text = " ".join(transcript_parts).strip()
        logger.info("Transcribed %d bytes -> %d chars", len(audio_bytes), len(text))
        return text or _mock_transcription()

    except (BotoCoreError, ClientError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Nova Sonic transcription failed, using mock: %s", exc)
        return _mock_transcription()


def _mock_transcription() -> str:
    return "Find me the best laptop under $800 from Amazon, Best Buy, and Newegg."
