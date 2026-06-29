"""Generic AI-provider backed read-only ticket analysis.

The current implementation supports OpenAI-compatible Responses API providers.
Additional providers can be added behind the same TicketImpactAnalyzer contract.
"""

import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.models.ticket import Ticket
from app.services.analysis import GeneratedTicketAnalysis, TicketImpactAnalyzer
from app.services.repository import RepositoryReader, RepositorySnapshot

MAX_FILES = 8
MAX_CHARS_PER_FILE = 6000
MAX_TOTAL_CHARS = 30_000


class AIProviderTicketImpactAnalyzer(TicketImpactAnalyzer):
    """Analyze ticket impact with an external AI provider using read-only repository context."""

    def __init__(self, repository_reader: RepositoryReader | None = None) -> None:
        self.repository_reader = repository_reader or RepositoryReader()

    async def analyze(self, ticket: Ticket) -> GeneratedTicketAnalysis:
        """Generate an AI analysis from the ticket and configured company repository."""
        if not settings.effective_ai_api_key:
            raise RuntimeError("AI_API_KEY is required when AI_PROVIDER is not mock")

        snapshot = await self.repository_reader.snapshot_for_company(
            ticket.company,
            f"{ticket.title}\n{ticket.description}",
        )
        code_context = await asyncio.to_thread(self._build_code_context, snapshot)
        payload = self._request_payload(ticket, snapshot, code_context)
        response_data = await asyncio.to_thread(self._call_openai_compatible_provider, payload)
        parsed = self._extract_json_response(response_data)
        return self._to_generated_analysis(ticket, snapshot, parsed)

    def _build_code_context(self, snapshot: RepositorySnapshot | None) -> str:
        if snapshot is None:
            return "No hay repositorio configurado para la empresa."
        if snapshot.read_error:
            return f"No se pudo leer el repositorio: {snapshot.read_error}"

        remaining_chars = MAX_TOTAL_CHARS
        chunks: list[str] = []
        for relative_path in snapshot.candidate_files[:MAX_FILES]:
            file_path = snapshot.local_path / relative_path
            if not self._is_inside_repo(file_path, snapshot.local_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            clipped_content = content[: min(MAX_CHARS_PER_FILE, remaining_chars)]
            remaining_chars -= len(clipped_content)
            chunks.append(f"### FILE: {relative_path}\n```text\n{clipped_content}\n```")
            if remaining_chars <= 0:
                break

        if not chunks:
            return "Repositorio leido, pero no se localizaron ficheros candidatos legibles."
        return "\n\n".join(chunks)

    def _is_inside_repo(self, file_path: Path, repo_path: Path) -> bool:
        try:
            file_path.resolve().relative_to(repo_path.resolve())
        except ValueError:
            return False
        return True

    def _request_payload(
        self,
        ticket: Ticket,
        snapshot: RepositorySnapshot | None,
        code_context: str,
    ) -> dict[str, Any]:
        company = ticket.company
        repo_url = company.repo_url if company else None
        branch = company.repo_branch if company and company.repo_branch else "master"
        repository_note = (
            f"Repositorio: {repo_url}\nRama: {branch}"
            if snapshot and not snapshot.read_error
            else "Repositorio no disponible o no configurado."
        )

        return {
            "model": settings.effective_ai_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente senior de ingenieria de software. "
                        "Analiza tickets contra codigo Python real. "
                        "Estima horas, complejidad y nivel requerido segun impacto tecnico, riesgo, "
                        "cantidad de ficheros afectados y necesidad de criterio arquitectonico. "
                        "Para cada cambio propuesto, localiza exactamente el bloque de codigo a tocar. "
                        "Devuelve current_code con el fragmento actual copiado del contexto, suggested_code con "
                        "el reemplazo propuesto e instructions con pasos concretos. "
                        "No respondas con frases genericas como 'revisar este archivo' si hay codigo suficiente. "
                        "Para cada cambio propuesto, devuelve tambien un diff unificado estilo git diff. "
                        "El diff debe mostrar lineas de contexto, lineas eliminadas con '-' y lineas nuevas con '+'. "
                        "Si no tienes suficiente contexto para un diff fiable, deja diff/current_code/suggested_code "
                        "vacios y explica el motivo "
                        "en summary/change. "
                        "Debes proponer cambios concretos de solo lectura: no ejecutes comandos, "
                        "no modifiques archivos, "
                        "no inventes ficheros si el contexto no los soporta. Devuelve JSON valido segun el esquema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Ticket #{ticket.id}\n"
                        f"Titulo: {ticket.title}\n"
                        f"Descripcion: {ticket.description}\n"
                        f"Tipo: {ticket.type.value}\n"
                        f"Prioridad: {ticket.priority.value}\n"
                        f"{repository_note}\n\n"
                        "Codigo candidato leido del repositorio:\n"
                        f"{code_context}"
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ticket_code_impact",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "complexity": {"type": "string", "enum": ["baja", "media", "alta"]},
                            "required_skill_level": {"type": "string", "enum": ["junior", "mid", "senior"]},
                            "estimated_hours": {"type": "integer"},
                            "affected_files": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "technical_summary": {"type": "string"},
                            "recommended_tasks": {"type": "array", "items": {"type": "string"}},
                            "proposed_changes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "file": {"type": "string"},
                                        "branch": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "change": {"type": "string"},
                                        "current_code": {"type": "string"},
                                        "suggested_code": {"type": "string"},
                                        "instructions": {"type": "array", "items": {"type": "string"}},
                                        "diff": {"type": "string"},
                                    },
                                    "required": [
                                        "file",
                                        "branch",
                                        "summary",
                                        "change",
                                        "current_code",
                                        "suggested_code",
                                        "instructions",
                                        "diff",
                                    ],
                                },
                            },
                        },
                        "required": [
                            "complexity",
                            "required_skill_level",
                            "estimated_hours",
                            "affected_files",
                            "risks",
                            "technical_summary",
                            "recommended_tasks",
                            "proposed_changes",
                        ],
                    },
                },
            },
        }

    def _call_openai_compatible_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{settings.ai_api_base_url.rstrip('/')}/responses"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {settings.effective_ai_api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.effective_ai_timeout_seconds) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"AI provider error {exc.code}: {detail}") from exc

    def _extract_json_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        output_text = response_data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return json.loads(output_text)

        text_chunks: list[str] = []
        for output_item in response_data.get("output", []):
            for content_item in output_item.get("content", []):
                if content_item.get("type") in {"output_text", "text"}:
                    text_chunks.append(content_item.get("text", ""))
        if not text_chunks:
            raise RuntimeError("AI provider response did not include output text")
        return json.loads("".join(text_chunks))

    def _to_generated_analysis(
        self,
        ticket: Ticket,
        snapshot: RepositorySnapshot | None,
        parsed: dict[str, Any],
    ) -> GeneratedTicketAnalysis:
        branch = ticket.company.repo_branch if ticket.company and ticket.company.repo_branch else "master"
        proposed_changes = parsed.get("proposed_changes") or []
        for change in proposed_changes:
            change.setdefault("branch", branch)
            change.setdefault("summary", change.get("change", ""))
            change.setdefault("change", change.get("summary", ""))
            change.setdefault("current_code", "")
            change.setdefault("suggested_code", "")
            change.setdefault("instructions", [])
            change.setdefault("diff", "")

        affected_files = parsed.get("affected_files") or []
        if not affected_files and snapshot and snapshot.candidate_files:
            affected_files = snapshot.candidate_files[:5]

        return GeneratedTicketAnalysis(
            complexity=str(parsed["complexity"]),
            required_skill_level=str(parsed["required_skill_level"]),
            estimated_hours=max(1, int(parsed["estimated_hours"])),
            affected_files=list(affected_files),
            risks=list(parsed.get("risks") or []),
            technical_summary=str(parsed["technical_summary"]),
            recommended_tasks=list(parsed.get("recommended_tasks") or []),
            proposed_changes=list(proposed_changes),
        )
