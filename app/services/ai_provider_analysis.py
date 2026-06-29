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

MAX_CHARS_PER_FILE = 18_000
MAX_TOTAL_CHARS = 80_000
MAX_FULL_FILE_CHARS = 14_000
MAX_REPO_MAP_FILES = 1200
SNIPPET_RADIUS_LINES = 70
MIN_LOCAL_CONTEXT_FILES = 2

SEARCH_SYNONYMS = {
    "actualizar": ["refrescar", "recargar", "refresh", "reload", "update"],
    "refrescar": ["actualizar", "recargar", "refresh", "reload", "update"],
    "boton": ["button", "btn", "pushbutton", "qpushbutton", "ttk.button"],
    "imagen": ["icono", "icon", "image", "png", "svg", "ico"],
    "icono": ["imagen", "icon", "image", "png", "svg", "ico"],
    "ventana": ["window", "frame", "pantalla", "screen"],
}


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
        if snapshot and not snapshot.read_error:
            planning = await asyncio.to_thread(self._local_context_plan, ticket, snapshot)
            if not self._has_enough_local_context(planning):
                planning_context = await asyncio.to_thread(self._build_planning_context, ticket, snapshot)
                planning_payload = self._planning_payload(ticket, snapshot, planning_context)
                planning_data = await asyncio.to_thread(self._call_openai_compatible_provider, planning_payload)
                planning = self._extract_json_response(planning_data)
            code_context = await asyncio.to_thread(self._build_targeted_code_context, ticket, snapshot, planning)
        else:
            code_context = await asyncio.to_thread(self._build_code_context, snapshot)
        payload = self._request_payload(ticket, snapshot, code_context)
        response_data = await asyncio.to_thread(self._call_openai_compatible_provider, payload)
        parsed = self._extract_json_response(response_data)
        return self._to_generated_analysis(ticket, snapshot, parsed)

    def _local_context_plan(self, ticket: Ticket, snapshot: RepositorySnapshot) -> dict[str, Any]:
        search_terms = self._expanded_search_terms(ticket, {"requested_searches": []})
        requested_files: list[str] = []
        scored_files: list[tuple[int, str]] = []
        text_files = snapshot.text_files or snapshot.candidate_files

        company = ticket.company
        configured_files = company.config_file_paths if company and company.config_file_paths else []
        requested_files.extend(configured_files)

        for relative_path in text_files:
            score = self._score_local_file(snapshot.local_path / relative_path, relative_path, search_terms)
            if score > 0:
                scored_files.append((-score, relative_path))

        scored_files.sort()
        requested_files.extend(relative_path for _, relative_path in scored_files[:12])

        for relative_path in snapshot.resource_files:
            lowered = relative_path.lower()
            if any(term in lowered for term in search_terms) or self._looks_like_likely_resource(relative_path):
                requested_files.append(relative_path)

        return {
            "requested_files": list(dict.fromkeys(requested_files)),
            "requested_searches": search_terms,
            "reason": "Plan local generado desde indice cacheado del repositorio.",
        }

    def _score_local_file(self, file_path: Path, relative_path: str, search_terms: list[str]) -> int:
        lowered_path = relative_path.lower()
        score = sum(4 for term in search_terms if term in lowered_path)
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")[:100_000].lower()
        except OSError:
            return score
        score += sum(1 for term in search_terms if term in content)
        return score

    def _has_enough_local_context(self, planning: dict[str, Any]) -> bool:
        requested_files = [file_path for file_path in planning.get("requested_files", []) if file_path]
        return len(requested_files) >= MIN_LOCAL_CONTEXT_FILES

    def _build_planning_context(self, ticket: Ticket, snapshot: RepositorySnapshot) -> str:
        company = ticket.company
        configured_files = company.config_file_paths if company and company.config_file_paths else []
        all_files = snapshot.all_files or snapshot.candidate_files
        visible_files = all_files[:MAX_REPO_MAP_FILES]
        truncated_note = "\n[ARBOL TRUNCADO]" if len(all_files) > len(visible_files) else ""
        text_candidates = set(snapshot.candidate_files)
        file_lines = [
            f"- {file_path}{' [text]' if file_path in text_candidates else ' [resource]'}"
            for file_path in visible_files
        ]
        return (
            "Ficheros configurados por empresa:\n"
            f"{chr(10).join(f'- {file_path}' for file_path in configured_files) or '- ninguno'}\n\n"
            "Arbol del repositorio:\n"
            f"{chr(10).join(file_lines)}{truncated_note}"
        )

    def _planning_payload(
        self,
        ticket: Ticket,
        snapshot: RepositorySnapshot,
        planning_context: str,
    ) -> dict[str, Any]:
        return {
            "model": settings.effective_ai_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Eres un localizador de contexto de codigo. No propongas fixes todavia. "
                        "A partir del ticket y del arbol del repo, decide que archivos, recursos y busquedas "
                        "necesita leer el siguiente paso. Incluye sinonimos y terminos tecnicos equivalentes: "
                        "por ejemplo actualizar/refrescar/refresh/reload, boton/button/btn, imagen/icono/icon. "
                        "Pide archivos concretos cuando el nombre parezca relevante, aunque no coincida literalmente."
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
                        f"Repositorio: {snapshot.repo_url}\n"
                        f"Rama: {snapshot.branch}\n\n"
                        f"{planning_context}"
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ticket_context_plan",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "requested_files": {"type": "array", "items": {"type": "string"}},
                            "requested_searches": {"type": "array", "items": {"type": "string"}},
                            "reason": {"type": "string"},
                        },
                        "required": ["requested_files", "requested_searches", "reason"],
                    },
                },
            },
        }

    def _build_code_context(self, snapshot: RepositorySnapshot | None) -> str:
        if snapshot is None:
            return "No hay repositorio configurado para la empresa."
        if snapshot.read_error:
            return f"No se pudo leer el repositorio: {snapshot.read_error}"

        remaining_chars = MAX_TOTAL_CHARS
        chunks: list[str] = []
        for relative_path in snapshot.candidate_files:
            file_path = snapshot.local_path / relative_path
            if not self._is_inside_repo(file_path, snapshot.local_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            clipped_content = content[: min(MAX_CHARS_PER_FILE, remaining_chars)]
            remaining_chars -= len(clipped_content)
            numbered_content = self._numbered_lines(clipped_content)
            truncated_note = "\n[CONTENIDO TRUNCADO]" if len(clipped_content) < len(content) else ""
            chunks.append(f"### FILE: {relative_path}\n```text\n{numbered_content}{truncated_note}\n```")
            if remaining_chars <= 0:
                break

        if not chunks:
            return "Repositorio leido, pero no se localizaron ficheros candidatos legibles."
        return "\n\n".join(chunks)

    def _build_targeted_code_context(
        self,
        ticket: Ticket,
        snapshot: RepositorySnapshot,
        planning: dict[str, Any],
    ) -> str:
        remaining_chars = MAX_TOTAL_CHARS
        chunks: list[str] = []
        candidate_files = set(snapshot.candidate_files)
        all_files = set(snapshot.all_files or snapshot.candidate_files)
        requested_files = self._ordered_requested_files(ticket, snapshot, planning)
        search_terms = self._expanded_search_terms(ticket, planning)

        for relative_path in requested_files:
            if remaining_chars <= 0:
                break
            if relative_path not in all_files:
                continue
            file_path = snapshot.local_path / relative_path
            if relative_path not in candidate_files:
                chunks.append(
                    f"### RESOURCE: {relative_path}\n"
                    "```text\nArchivo no textual o binario; no se envia contenido.\n```",
                )
                remaining_chars -= len(chunks[-1])
                continue
            chunk = self._format_smart_file_context(
                file_path,
                snapshot.local_path,
                relative_path,
                search_terms,
                remaining_chars,
            )
            if chunk:
                chunks.append(chunk)
                remaining_chars -= len(chunk)

        used_files = set(requested_files)
        for relative_path in snapshot.candidate_files:
            if remaining_chars <= 0:
                break
            if relative_path in used_files:
                continue
            chunk = self._format_search_snippets(
                snapshot.local_path / relative_path,
                snapshot.local_path,
                relative_path,
                search_terms,
                remaining_chars,
            )
            if chunk:
                chunks.append(chunk)
                remaining_chars -= len(chunk)

        if not chunks:
            return self._build_code_context(snapshot)

        return (
            "Contexto localizado en dos fases. Primero se eligieron archivos/busquedas; "
            "despues el backend extrajo archivos completos y snippets con lineas numeradas.\n\n"
            + "\n\n".join(chunks)
        )

    def _ordered_requested_files(
        self,
        ticket: Ticket,
        snapshot: RepositorySnapshot,
        planning: dict[str, Any],
    ) -> list[str]:
        company = ticket.company
        configured_files = company.config_file_paths if company and company.config_file_paths else []
        requested_files = [
            str(file_path).strip().replace("\\", "/")
            for file_path in planning.get("requested_files", [])
        ]
        likely_files = [
            file_path
            for file_path in (snapshot.all_files or snapshot.candidate_files)
            if self._looks_like_likely_resource(file_path)
        ]
        return list(dict.fromkeys([*configured_files, *requested_files, *likely_files]))

    def _looks_like_likely_resource(self, file_path: str) -> bool:
        lowered = file_path.lower()
        return any(part in lowered for part in ("imagen", "image", "icon", "asset", "resource", "recurso"))

    def _expanded_search_terms(self, ticket: Ticket, planning: dict[str, Any]) -> list[str]:
        raw_terms = [
            *str(ticket.title).replace("_", " ").replace("-", " ").split(),
            *str(ticket.description).replace("_", " ").replace("-", " ").split(),
            *[str(term) for term in planning.get("requested_searches", [])],
        ]
        terms: list[str] = []
        for term in raw_terms:
            normalized = term.strip().lower().strip(".,:;()[]{}'\"")
            if len(normalized) < 3:
                continue
            terms.append(normalized)
            terms.extend(SEARCH_SYNONYMS.get(normalized, []))
        return list(dict.fromkeys(terms))

    def _format_file_chunk(
        self,
        file_path: Path,
        repo_path: Path,
        relative_path: str,
        remaining_chars: int,
    ) -> str:
        if not self._is_inside_repo(file_path, repo_path):
            return ""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
        clipped_content = content[: min(MAX_CHARS_PER_FILE, remaining_chars)]
        numbered_content = self._numbered_lines(clipped_content)
        truncated_note = "\n[CONTENIDO TRUNCADO]" if len(clipped_content) < len(content) else ""
        return f"### FILE: {relative_path}\n```text\n{numbered_content}{truncated_note}\n```"

    def _format_smart_file_context(
        self,
        file_path: Path,
        repo_path: Path,
        relative_path: str,
        search_terms: list[str],
        remaining_chars: int,
    ) -> str:
        if not self._is_inside_repo(file_path, repo_path):
            return ""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

        if len(content) <= min(MAX_FULL_FILE_CHARS, remaining_chars):
            return self._format_file_chunk(file_path, repo_path, relative_path, remaining_chars)

        snippets = self._format_search_snippets(file_path, repo_path, relative_path, search_terms, remaining_chars)
        if snippets:
            return snippets

        symbol_overview = self._format_symbol_overview(content, relative_path)
        head = "\n".join(f"{index + 1:04d}: {line}" for index, line in enumerate(content.splitlines()[:80]))
        return (
            f"### LARGE FILE SUMMARY: {relative_path}\n"
            "```text\n"
            "Archivo grande; se envia resumen de simbolos e inicio del fichero. "
            "Si necesitas lineas concretas, pidelas en requested_searches.\n\n"
            f"{symbol_overview}\n\n@@ inicio\n{head}\n```"
        )[:remaining_chars]

    def _format_symbol_overview(self, content: str, relative_path: str) -> str:
        symbol_prefixes = (
            "def ",
            "class ",
            "async def ",
            "function ",
            "export function ",
            "const ",
            "let ",
            "var ",
        )
        lines: list[str] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            lowered = stripped.lower()
            if any(lowered.startswith(prefix) for prefix in symbol_prefixes) or self._looks_like_ui_line(lowered):
                lines.append(f"{line_number:04d}: {stripped}")
            if len(lines) >= 120:
                break
        if not lines:
            return f"Sin simbolos detectados en {relative_path}."
        return "@@ simbolos y lineas relevantes\n" + "\n".join(lines)

    def _looks_like_ui_line(self, lowered_line: str) -> bool:
        ui_terms = ("button", "boton", "btn", ".png", ".svg", ".ico", "icon", "imagen", "obtener_recurso")
        return any(term in lowered_line for term in ui_terms)

    def _format_search_snippets(
        self,
        file_path: Path,
        repo_path: Path,
        relative_path: str,
        search_terms: list[str],
        remaining_chars: int,
    ) -> str:
        if not self._is_inside_repo(file_path, repo_path):
            return ""
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return ""

        matching_indexes = [
            index
            for index, line in enumerate(lines)
            if any(term in line.lower() for term in search_terms)
        ]
        if not matching_indexes:
            return ""

        ranges: list[tuple[int, int]] = []
        for index in matching_indexes[:8]:
            start = max(0, index - SNIPPET_RADIUS_LINES)
            end = min(len(lines), index + SNIPPET_RADIUS_LINES + 1)
            if ranges and start <= ranges[-1][1]:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
            else:
                ranges.append((start, end))

        snippets: list[str] = []
        for start, end in ranges:
            body = "\n".join(f"{line_number + 1:04d}: {lines[line_number]}" for line_number in range(start, end))
            snippets.append(f"@@ lineas {start + 1}-{end}\n{body}")
        chunk = f"### SNIPPETS: {relative_path}\n```text\n{chr(10).join(snippets)}\n```"
        return chunk[:remaining_chars]

    def _numbered_lines(self, content: str) -> str:
        return "\n".join(f"{line_number:04d}: {line}" for line_number, line in enumerate(content.splitlines(), start=1))

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
                        "Usa los numeros de linea incluidos en el contexto y rellena line_start y line_end. "
                        "Devuelve current_code con el fragmento actual copiado del contexto, suggested_code con "
                        "el reemplazo propuesto e instructions con pasos concretos. "
                        "Cuando el cambio sea de recursos/imagenes/configuracion, incluye target_path con la ruta "
                        "exacta del recurso o fichero que se debe anadir/sustituir. "
                        "Las instrucciones deben ser accionables: por ejemplo, 'lineas 120-124: sustituir X por Y' "
                        "y 'anadir archivo imagenes/nuevo_refrescar.png'. "
                        "No respondas con frases genericas como 'revisar este archivo' si hay codigo suficiente. "
                        "No incluyas git diff; la salida debe centrarse en lineas, instrucciones, codigo actual "
                        "y codigo propuesto. "
                        "Si no tienes suficiente contexto para un cambio fiable, deja current_code/suggested_code "
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
                                        "line_start": {"type": "integer"},
                                        "line_end": {"type": "integer"},
                                        "target_path": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "change": {"type": "string"},
                                        "current_code": {"type": "string"},
                                        "suggested_code": {"type": "string"},
                                        "instructions": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": [
                                        "file",
                                        "branch",
                                        "line_start",
                                        "line_end",
                                        "target_path",
                                        "summary",
                                        "change",
                                        "current_code",
                                        "suggested_code",
                                        "instructions",
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
            change.setdefault("line_start", 0)
            change.setdefault("line_end", 0)
            change.setdefault("target_path", "")
            change.setdefault("summary", change.get("change", ""))
            change.setdefault("change", change.get("summary", ""))
            change.setdefault("current_code", "")
            change.setdefault("suggested_code", "")
            change.setdefault("instructions", [])

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
