"""Provider request adapters.

Adapters in this module only serialize requests. They contain no HTTP client,
credential lookup, or network code, so running them cannot call a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hashing import canonical_json, sha256_json
from .models import PacketBuildResult


class RequestPreparationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedRequest:
    provider: str
    endpoint: str
    body: dict[str, Any]
    model_visible_payload: dict[str, Any]
    request_hash: str
    model_visible_hash: str
    source_packet_hash: str
    network_enabled: bool = False


class OpenAIResponsesDryRunAdapter:
    """Serialize a stateless Responses API request without sending it."""

    provider = "openai"
    endpoint = "POST /v1/responses"
    instructions = (
        "Act only as the anonymous participant described in the participant "
        "packet. Make one choice. Return only the structured response requested."
    )

    def __init__(
        self,
        model_snapshot: str = "DRY_RUN_MODEL_NOT_SELECTED",
        *,
        temperature: float | None = None,
        max_output_tokens: int = 64,
    ):
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens_must_be_positive")
        self.model_snapshot = model_snapshot
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def prepare(
        self,
        result: PacketBuildResult,
        *,
        study_id: str,
        contract_version: str,
    ) -> PreparedRequest:
        if result.status != "ready" or not result.packet_hash:
            raise RequestPreparationError("packet_not_sendable")
        schema = result.packet.get("response_schema")
        if not isinstance(schema, dict):
            raise RequestPreparationError("response_schema_missing")

        # The official Responses API accepts string input and configures
        # Structured Outputs under text.format. Conversation state, previous
        # response IDs, and tools are deliberately absent from this request.
        packet_text = canonical_json(result.packet)
        body: dict[str, Any] = {
            "model": self.model_snapshot,
            "instructions": self.instructions,
            "input": packet_text,
            "reasoning": {"effort": "none"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "participant_choice",
                    "strict": True,
                    "schema": schema,
                }
            },
            "tools": [],
            "tool_choice": "none",
            "store": False,
            "max_output_tokens": self.max_output_tokens,
            "metadata": {
                "study_id": study_id,
                "contract_version": contract_version,
                "packet_hash": result.packet_hash,
                "dry_run": "true",
            },
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        model_visible_payload = {
            "instructions": body["instructions"],
            "input": body["input"],
            "text": body["text"],
        }
        return PreparedRequest(
            provider=self.provider,
            endpoint=self.endpoint,
            body=body,
            model_visible_payload=model_visible_payload,
            request_hash=sha256_json(body),
            model_visible_hash=sha256_json(model_visible_payload),
            source_packet_hash=result.packet_hash,
        )


FORBIDDEN_STATE_FIELDS = {
    "conversation",
    "previous_response_id",
    "prompt",
}


def validate_stateless_request(prepared: PreparedRequest) -> list[str]:
    """Return request-envelope violations; an empty list is sendable."""

    violations: list[str] = []
    for field in sorted(FORBIDDEN_STATE_FIELDS):
        if field in prepared.body:
            violations.append(f"state_field_present:{field}")
    if prepared.body.get("store") is not False:
        violations.append("store_must_be_false")
    if prepared.body.get("tools") != []:
        violations.append("tools_must_be_empty")
    if prepared.body.get("tool_choice") != "none":
        violations.append("tool_choice_must_be_none")
    if prepared.network_enabled:
        violations.append("dry_run_network_must_be_disabled")
    return violations
