"""Streamlit demo frontend for AI SmartEC Tickets."""

import json
import os
from datetime import datetime
from typing import Any

import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", API_BASE_URL).replace("http://api:8000", "http://localhost:8000")
TIMEOUT_SECONDS = 10

TICKET_TYPES = ["historia_usuario", "tarea", "incidencia", "bug"]
TICKET_PRIORITIES = ["baja", "media", "alta", "urgente"]
USER_SKILL_LEVELS = ["junior", "mid", "senior"]
BOARD_STATUSES = ["pendiente", "en_curso", "pruebas_internas", "qa", "desplegado"]
CLOSED_STATUS = "cierre"
TICKET_STATUSES = [*BOARD_STATUSES, CLOSED_STATUS]
STATUS_LABELS = {
    "pendiente": "Pendiente",
    "en_curso": "En curso",
    "pruebas_internas": "Pruebas internas",
    "qa": "QA",
    "desplegado": "Desplegado",
    "cierre": "Cierre",
}


def auth_headers() -> dict[str, str]:
    """Return authorization headers for the current Streamlit session."""
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    """Call the FastAPI backend and return decoded JSON when available."""
    url = f"{API_BASE_URL}{path}"
    headers = {**auth_headers(), **kwargs.pop("headers", {})}
    response = requests.request(method, url, timeout=TIMEOUT_SECONDS, headers=headers, **kwargs)
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError(f"{response.status_code}: {detail}")
    if response.status_code == 204:
        return None
    return response.json()


def load_companies() -> list[dict[str, Any]]:
    """Fetch companies from the API."""
    return api_request("GET", "/companies")


def load_tickets() -> list[dict[str, Any]]:
    """Fetch tickets from the API."""
    return api_request("GET", "/tickets")


def load_users() -> list[dict[str, Any]]:
    """Fetch users from the API."""
    return api_request("GET", "/users")


def parse_config_paths(value: str) -> list[str]:
    """Parse comma/newline separated config paths."""
    normalized = value.replace(",", "\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def load_ticket_analyses(ticket_id: int) -> list[dict[str, Any]]:
    """Fetch analyses for a ticket."""
    return api_request("GET", f"/tickets/{ticket_id}/analyses")


def is_admin() -> bool:
    """Return whether the authenticated user has admin permissions."""
    return st.session_state.get("current_user", {}).get("role") == "admin"


def render_login() -> None:
    """Render real login form."""
    st.set_page_config(page_title="AI SmartEC Tickets", layout="centered")
    st.title("AI SmartEC Tickets")
    st.caption("Acceso interno")

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")

    if submitted:
        try:
            login = api_request("POST", "/auth/login", json={"username": username, "password": password})
        except Exception as exc:
            st.error(f"No se pudo iniciar sesion: {exc}")
            return

        st.session_state["access_token"] = login["access_token"]
        st.session_state["current_user"] = login["user"]
        st.rerun()


def render_status() -> None:
    """Render API connectivity and session status."""
    try:
        health = api_request("GET", "/health")
    except Exception as exc:
        st.error(f"No se puede conectar con la API en {API_BASE_URL}. Detalle: {exc}")
        st.stop()

    user = st.session_state["current_user"]
    st.sidebar.caption(f"API: {API_BASE_URL}")
    st.sidebar.caption(f"Estado: {health['status']}")
    st.sidebar.markdown(f"**Usuario:** {user['username']}")
    st.sidebar.caption(f"Rol: {user['role']}")
    if st.sidebar.button("Cerrar sesion"):
        st.session_state.clear()
        st.rerun()


def render_companies_tab(can_manage: bool) -> None:
    """Render company list and creation form."""
    st.subheader("Empresas")

    try:
        companies = load_companies()
    except Exception as exc:
        st.error(f"No se pudieron cargar empresas: {exc}")
        return

    if companies:
        visible_companies = [
            {
                "nombre": company["name"],
                "codigo": company["code"],
                "descripcion": company["description"],
                "repo_url": company["repo_url"],
                "rama_repo": company["repo_branch"],
                "configs": "\n".join(company["config_file_paths"] or []),
                "creado": company["created_at"],
            }
            for company in companies
        ]
        st.dataframe(visible_companies, use_container_width=True, hide_index=True)
    else:
        st.info("Todavia no hay empresas creadas.")

    with st.expander("Crear empresa"):
        with st.form("create_company_form", clear_on_submit=True):
            name = st.text_input("Nombre", placeholder="Iberdrola")
            code = st.text_input("Codigo", placeholder="IBE").upper()
            repo_url = st.text_input("URL del repo", placeholder="https://github.com/org/repo.git")
            repo_branch = st.text_input("Rama del repo", placeholder="feature/iberdrola")
            config_paths = st.text_area(
                "Ficheros de configuracion",
                placeholder="config.json, configuracion.py, rutas.py",
            )
            description = st.text_area("Descripcion", placeholder="Empresa electrica para demo.")
            submitted = st.form_submit_button("Crear empresa")

        if submitted:
            try:
                api_request(
                    "POST",
                    "/companies",
                    json={
                        "name": name,
                        "code": code,
                        "description": description or None,
                        "repo_url": repo_url or None,
                        "repo_branch": repo_branch or None,
                        "config_file_paths": parse_config_paths(config_paths),
                    },
                )
            except Exception as exc:
                st.error(f"No se pudo crear la empresa: {exc}")
            else:
                st.success("Empresa creada correctamente.")
                st.rerun()

    if companies:
        with st.expander("Editar empresa"):
            company_options = {f"{company['name']} ({company['code']})": company for company in companies}
            selected_label = st.selectbox("Empresa", options=list(company_options), key="edit_company_select")
            selected_company = company_options[selected_label]
            selected_company_id = selected_company["id"]

            with st.form("edit_company_form"):
                name = st.text_input(
                    "Nombre",
                    value=selected_company["name"],
                    key=f"edit_company_name_{selected_company_id}",
                )
                code = st.text_input(
                    "Codigo",
                    value=selected_company["code"],
                    key=f"edit_company_code_{selected_company_id}",
                ).upper()
                repo_branch = st.text_input(
                    "Rama del repo",
                    value=selected_company["repo_branch"] or "",
                    key=f"edit_company_branch_{selected_company_id}",
                )
                repo_url = st.text_input(
                    "URL del repo",
                    value=selected_company["repo_url"] or "",
                    key=f"edit_company_repo_url_{selected_company_id}",
                )
                config_paths = st.text_area(
                    "Ficheros de configuracion",
                    value="\n".join(selected_company["config_file_paths"] or []),
                    key=f"edit_company_config_paths_{selected_company_id}",
                )
                description = st.text_area(
                    "Descripcion",
                    value=selected_company["description"] or "",
                    key=f"edit_company_description_{selected_company_id}",
                )
                submitted = st.form_submit_button("Guardar cambios")

            if submitted:
                try:
                    api_request(
                        "PUT",
                        f"/companies/{selected_company_id}",
                        json={
                            "name": name,
                            "code": code,
                            "description": description or None,
                            "repo_url": repo_url or None,
                            "repo_branch": repo_branch or None,
                            "config_file_paths": parse_config_paths(config_paths),
                        },
                    )
                except Exception as exc:
                    st.error(f"No se pudo editar la empresa: {exc}")
                else:
                    st.success("Empresa actualizada correctamente.")
                    st.rerun()

    if can_manage and companies:
        with st.expander("Eliminar empresa"):
            company_options = {f"{company['name']} ({company['code']})": company["id"] for company in companies}
            selected_company = st.selectbox("Empresa", options=list(company_options), key="delete_company_select")
            if st.button("Eliminar empresa", type="secondary"):
                try:
                    api_request("DELETE", f"/companies/{company_options[selected_company]}")
                except Exception as exc:
                    st.error(f"No se pudo eliminar la empresa: {exc}")
                else:
                    st.success("Empresa eliminada.")
                    st.rerun()


def render_tickets_tab() -> None:
    """Render ticket list and creation form."""
    st.subheader("Crear ticket")

    try:
        companies = load_companies()
        users = load_users()
    except Exception as exc:
        st.error(f"No se pudieron cargar datos: {exc}")
        return

    if not companies:
        st.warning("Crea al menos una empresa antes de crear tickets.")
        return

    company_options = {f"{company['name']} ({company['code']})": company["id"] for company in companies}
    user_options = {"Asignacion automatica": None} | {user["username"]: user["id"] for user in users if user["is_active"]}

    with st.form("create_ticket_form", clear_on_submit=True):
        title = st.text_input("Titulo", placeholder="Alta de nuevo suministro")
        description = st.text_area(
            "Descripcion",
            placeholder="Gestionar validaciones tecnicas para un nuevo punto de suministro.",
        )
        company_label = st.selectbox("Empresa", options=list(company_options))
        ticket_type = st.selectbox("Tipo", options=TICKET_TYPES)
        priority = st.selectbox("Prioridad", options=TICKET_PRIORITIES, index=1)
        assigned_user = st.selectbox("Usuario asignado", options=list(user_options))
        submitted = st.form_submit_button("Crear ticket y analizar")

    if submitted:
        try:
            created_ticket = api_request(
                "POST",
                "/tickets",
                json={
                    "title": title,
                    "description": description,
                    "company_id": company_options[company_label],
                    "type": ticket_type,
                    "priority": priority,
                    "assigned_user_id": user_options[assigned_user],
                },
            )
            analyses = load_ticket_analyses(created_ticket["id"])
        except Exception as exc:
            st.error(f"No se pudo crear el ticket: {exc}")
        else:
            if created_ticket.get("analysis_error"):
                st.toast(created_ticket["analysis_error"])
                st.error(created_ticket["analysis_error"])
            elif analyses:
                st.success("Ticket creado, asignado y analizado correctamente.")
            else:
                st.warning("Ticket creado sin analisis IA. Puedes reintentar la valoracion desde el ticket.")
            st.rerun()


def build_board_html(
    tickets: list[dict[str, Any]],
    users: list[dict[str, Any]],
    companies: list[dict[str, Any]],
    analyses_by_ticket: dict[str, list[dict[str, Any]]],
    can_manage: bool,
) -> str:
    """Build the drag/drop board component."""
    payload = {
        "apiBase": PUBLIC_API_BASE_URL,
        "token": st.session_state["access_token"],
        "tickets": tickets,
        "users": users,
        "companies": companies,
        "analysesByTicket": analyses_by_ticket,
        "statuses": BOARD_STATUSES,
        "allStatuses": TICKET_STATUSES,
        "statusLabels": STATUS_LABELS,
        "ticketTypes": TICKET_TYPES,
        "priorities": TICKET_PRIORITIES,
        "canManage": can_manage,
    }
    encoded_payload = json.dumps(payload).replace("</", "<\\/")
    return f"""
<!doctype html>
<html>
<head>
<style>
  body {{ margin: 0; font-family: Inter, Arial, sans-serif; color: #17202a; background: #f6f8fa; }}
  .board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; overflow-x: auto; }}
  .column {{ min-height: 620px; background: #edf1f5; border: 1px solid #d9e0e8; border-radius: 8px; padding: 10px; }}
  .column.drag-over {{ outline: 2px solid #2474d2; background: #e7f0fb; }}
  .column-title {{ font-size: 13px; font-weight: 700; margin-bottom: 4px; }}
  .column-count {{ font-size: 12px; color: #5f6f7f; margin-bottom: 10px; }}
  .card {{ background: white; border: 1px solid #d8dee6; border-radius: 8px; padding: 10px; margin-bottom: 10px; cursor: grab; }}
  .card:active {{ cursor: grabbing; }}
  .card-title {{ font-weight: 700; font-size: 13px; margin-bottom: 8px; }}
  .meta {{ color: #5f6f7f; font-size: 12px; line-height: 1.35; }}
  .pill {{ display: inline-block; border-radius: 999px; background: #eef2f7; padding: 2px 7px; margin: 2px 3px 2px 0; }}
  .modal-backdrop {{ display: none; position: fixed; inset: 0; background: rgba(9, 18, 28, .46); z-index: 10; }}
  .modal {{ position: absolute; left: 50%; top: 48%; transform: translate(-50%, -50%); width: min(980px, 94vw);
    max-height: 88vh; overflow: auto; background: white; border-radius: 8px; padding: 18px; box-shadow: 0 20px 60px rgba(0,0,0,.25); }}
  .modal-header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
  .modal-title {{ font-size: 18px; font-weight: 750; }}
  .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
  label {{ display: block; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
  input, textarea, select {{ width: 100%; box-sizing: border-box; border: 1px solid #cfd7e2; border-radius: 6px; padding: 8px; font: inherit; }}
  textarea {{ min-height: 110px; resize: vertical; }}
  button {{ border: 1px solid #c8d1dc; background: white; border-radius: 6px; padding: 8px 10px; cursor: pointer; font-weight: 650; }}
  button.primary {{ background: #1f6feb; color: white; border-color: #1f6feb; }}
  button.danger {{ background: #cf222e; color: white; border-color: #cf222e; }}
  .actions {{ display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }}
  .analysis {{ margin-top: 16px; padding-top: 12px; border-top: 1px solid #e1e7ef; }}
  .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }}
  .metric {{ background: #f6f8fa; border: 1px solid #e1e7ef; border-radius: 8px; padding: 10px; }}
  .metric strong {{ display: block; font-size: 12px; color: #5f6f7f; }}
  pre {{ white-space: pre-wrap; background: #f6f8fa; border: 1px solid #e1e7ef; border-radius: 8px; padding: 10px; }}
  ul {{ margin-top: 6px; }}
  .hint {{ font-size: 12px; color: #5f6f7f; margin-bottom: 12px; }}
</style>
</head>
<body>
<div class="hint">Arrastra tarjetas entre columnas. Doble click en una tarjeta para editarla y ver analisis/propuesta.</div>
<div id="board" class="board"></div>
<div id="modalBackdrop" class="modal-backdrop"></div>
<script>
const state = {encoded_payload};
let tickets = state.tickets;
const usersById = Object.fromEntries(state.users.map(user => [user.id, user]));
const companiesById = Object.fromEntries(state.companies.map(company => [company.id, company]));

function api(path, options = {{}}) {{
  const headers = Object.assign({{
    "Content-Type": "application/json",
    "Authorization": `Bearer ${{state.token}}`
  }}, options.headers || {{}});
  return fetch(`${{state.apiBase}}${{path}}`, Object.assign({{}}, options, {{headers}})).then(async response => {{
    if (!response.ok) {{
      const text = await response.text();
      try {{
        const payload = JSON.parse(text);
        throw new Error(payload.detail || text);
      }} catch (error) {{
        if (error instanceof SyntaxError) throw new Error(`${{response.status}}: ${{text}}`);
        throw error;
      }}
    }}
    if (response.status === 204) return null;
    return response.json();
  }});
}}

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, char => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#039;"}}[char]));
}}

function renderBoard() {{
  const board = document.getElementById("board");
  board.innerHTML = "";
  for (const status of state.statuses) {{
    const column = document.createElement("section");
    column.className = "column";
    column.dataset.status = status;
    const matching = tickets.filter(ticket => ticket.status === status);
    column.innerHTML = `<div class="column-title">${{state.statusLabels[status]}}</div><div class="column-count">${{matching.length}} tickets</div>`;
    column.addEventListener("dragover", event => {{
      event.preventDefault();
      column.classList.add("drag-over");
    }});
    column.addEventListener("dragleave", () => column.classList.remove("drag-over"));
    column.addEventListener("drop", async event => {{
      event.preventDefault();
      column.classList.remove("drag-over");
      const ticketId = Number(event.dataTransfer.getData("text/plain"));
      const ticket = tickets.find(item => item.id === ticketId);
      if (!ticket || ticket.status === status) return;
      const previousStatus = ticket.status;
      ticket.status = status;
      renderBoard();
      try {{
        await api(`/tickets/${{ticketId}}`, {{method: "PUT", body: JSON.stringify({{status}})}});
      }} catch (error) {{
        ticket.status = previousStatus;
        renderBoard();
        alert(`No se pudo mover el ticket: ${{error.message}}`);
      }}
    }});
    for (const ticket of matching) {{
      const card = document.createElement("article");
      card.className = "card";
      card.draggable = true;
      card.dataset.ticketId = ticket.id;
      const company = companiesById[ticket.company_id]?.code || `Empresa ${{ticket.company_id}}`;
      const assignee = usersById[ticket.assigned_user_id]?.username || ticket.assigned_to || "Sin asignar";
      card.innerHTML = `
        <div class="card-title">#${{ticket.id}} ${{escapeHtml(ticket.title)}}</div>
        <div class="meta"><span class="pill">${{escapeHtml(company)}}</span><span class="pill">${{ticket.type}}</span><span class="pill">${{ticket.priority}}</span></div>
        <div class="meta">Asignado: ${{escapeHtml(assignee)}}</div>
      `;
      card.addEventListener("dragstart", event => event.dataTransfer.setData("text/plain", String(ticket.id)));
      card.addEventListener("dblclick", () => openModal(ticket.id));
      column.appendChild(card);
    }}
    board.appendChild(column);
  }}
}}

function optionList(options, selected) {{
  return options.map(value => `<option value="${{value}}" ${{value === selected ? "selected" : ""}}>${{value}}</option>`).join("");
}}

function userOptionList(selected) {{
  const empty = `<option value="">Sin asignar</option>`;
  return empty + state.users.filter(user => user.is_active).map(user => (
    `<option value="${{user.id}}" ${{user.id === selected ? "selected" : ""}}>${{escapeHtml(user.username)}}</option>`
  )).join("");
}}

function latestAnalysis(ticketId) {{
  const analyses = state.analysesByTicket[String(ticketId)] || [];
  return analyses.length ? analyses[0] : null;
}}

function renderAnalysis(ticketId) {{
  const analysis = latestAnalysis(ticketId);
  if (!analysis) return "<div class='analysis'><strong>Analisis</strong><p>No hay analisis guardado.</p></div>";
  const files = analysis.affected_files.map(file => `<li><code>${{escapeHtml(file)}}</code></li>`).join("");
  const risks = analysis.risks.map(risk => `<li>${{escapeHtml(risk)}}</li>`).join("");
  const tasks = analysis.recommended_tasks.map(task => `<li>${{escapeHtml(task)}}</li>`).join("");
  const changes = analysis.proposed_changes.map(change => {{
    const instructions = (change.instructions || []).map(item => `<li>${{escapeHtml(item)}}</li>`).join("");
    const currentCode = change.current_code ? `<h5>Codigo actual</h5><pre>${{escapeHtml(change.current_code)}}</pre>` : "";
    const suggestedCode = change.suggested_code ? `<h5>Codigo propuesto</h5><pre>${{escapeHtml(change.suggested_code)}}</pre>` : "";
    const diff = change.diff ? `<h5>Diff sugerido</h5><pre>${{escapeHtml(change.diff)}}</pre>` : "";
    const fallback = !change.current_code && !change.suggested_code && !change.diff ? `<pre>${{escapeHtml(change.change)}}</pre>` : "";
    return `<h4>${{escapeHtml(change.file)}} (${{escapeHtml(change.branch)}})</h4>
      ${{change.summary ? `<p>${{escapeHtml(change.summary)}}</p>` : ""}}
      ${{instructions ? `<h5>Pasos</h5><ul>${{instructions}}</ul>` : ""}}
      ${{currentCode}}${{suggestedCode}}${{diff}}${{fallback}}`;
  }}).join("");
  return `
    <div class="analysis">
      <div class="metrics">
        <div class="metric"><strong>Complejidad</strong>${{escapeHtml(analysis.complexity)}}</div>
        <div class="metric"><strong>Nivel</strong>${{escapeHtml(analysis.required_skill_level || "-")}}</div>
        <div class="metric"><strong>Horas</strong>${{analysis.estimated_hours}}</div>
        <div class="metric"><strong>Ticket</strong>#${{analysis.ticket_id}}</div>
      </div>
      <h3>Resumen tecnico</h3><pre>${{escapeHtml(analysis.technical_summary)}}</pre>
      <div class="grid"><div><h3>Archivos afectados</h3><ul>${{files}}</ul></div><div><h3>Riesgos</h3><ul>${{risks}}</ul></div></div>
      <h3>Tareas recomendadas</h3><ul>${{tasks}}</ul>
      <h3>Propuesta IA</h3>${{changes}}
    </div>
  `;
}}

function openModal(ticketId) {{
  const ticket = tickets.find(item => item.id === ticketId);
  const backdrop = document.getElementById("modalBackdrop");
  backdrop.style.display = "block";
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <div class="modal-title">#${{ticket.id}} ${{escapeHtml(ticket.title)}}</div>
        <button id="closeModal">Cerrar</button>
      </div>
      <div class="grid">
        <div><label>Titulo</label><input id="editTitle" value="${{escapeHtml(ticket.title)}}"></div>
        <div><label>Estado</label><select id="editStatus">${{optionList(state.allStatuses, ticket.status)}}</select></div>
        <div><label>Tipo</label><select id="editType">${{optionList(state.ticketTypes, ticket.type)}}</select></div>
        <div><label>Prioridad</label><select id="editPriority">${{optionList(state.priorities, ticket.priority)}}</select></div>
        <div><label>Asignado a</label><select id="editAssignee">${{userOptionList(ticket.assigned_user_id)}}</select></div>
        <div><label>Empresa</label><input value="${{escapeHtml(companiesById[ticket.company_id]?.name || ticket.company_id)}}" disabled></div>
      </div>
      <div style="margin-top:12px"><label>Descripcion</label><textarea id="editDescription">${{escapeHtml(ticket.description)}}</textarea></div>
      ${{renderAnalysis(ticket.id)}}
      <div class="actions">
        ${{state.canManage ? '<button id="deleteTicket" class="danger">Eliminar tarea</button>' : ''}}
        <button id="analyzeTicket">Analizar IA</button>
        <button id="saveTicket" class="primary">Guardar cambios</button>
      </div>
    </div>
  `;
  document.getElementById("closeModal").onclick = () => backdrop.style.display = "none";
  document.getElementById("analyzeTicket").onclick = async () => {{
    try {{
      const analysis = await api(`/tickets/${{ticket.id}}/analyze`, {{method: "POST"}});
      const updated = await api(`/tickets/${{ticket.id}}`);
      state.analysesByTicket[String(ticket.id)] = [analysis, ...(state.analysesByTicket[String(ticket.id)] || [])];
      tickets = tickets.map(item => item.id === updated.id ? updated : item);
      renderBoard();
      openModal(ticket.id);
    }} catch (error) {{
      alert(`No se pudo analizar el ticket: ${{error.message}}`);
    }}
  }};
  document.getElementById("saveTicket").onclick = async () => {{
    const assignedValue = document.getElementById("editAssignee").value;
    const payload = {{
      title: document.getElementById("editTitle").value,
      description: document.getElementById("editDescription").value,
      status: document.getElementById("editStatus").value,
      type: document.getElementById("editType").value,
      priority: document.getElementById("editPriority").value,
      assigned_user_id: assignedValue ? Number(assignedValue) : null
    }};
    try {{
      const updated = await api(`/tickets/${{ticket.id}}`, {{method: "PUT", body: JSON.stringify(payload)}});
      tickets = tickets.map(item => item.id === updated.id ? updated : item);
      backdrop.style.display = "none";
      renderBoard();
    }} catch (error) {{
      alert(`No se pudo guardar: ${{error.message}}`);
    }}
  }};
  const deleteButton = document.getElementById("deleteTicket");
  if (deleteButton) {{
    deleteButton.onclick = async () => {{
      if (!confirm("Eliminar esta tarea?")) return;
      try {{
        await api(`/tickets/${{ticket.id}}`, {{method: "DELETE"}});
        tickets = tickets.filter(item => item.id !== ticket.id);
        backdrop.style.display = "none";
        renderBoard();
      }} catch (error) {{
        alert(`No se pudo eliminar: ${{error.message}}`);
      }}
    }};
  }}
}}

renderBoard();
</script>
</body>
</html>
"""


def render_board_tab(can_manage: bool) -> None:
    """Render a Jira-like board with drag/drop and edit modal."""
    st.subheader("Tablero")

    try:
        tickets = [ticket for ticket in load_tickets() if ticket["status"] != CLOSED_STATUS]
        users = load_users()
        companies = load_companies()
        analyses_by_ticket = {str(ticket["id"]): load_ticket_analyses(ticket["id"]) for ticket in tickets}
    except Exception as exc:
        st.error(f"No se pudo cargar el tablero: {exc}")
        return

    components.html(
        build_board_html(tickets, users, companies, analyses_by_ticket, can_manage),
        height=780,
        scrolling=True,
    )


def parse_api_datetime(value: str) -> datetime:
    """Parse an API datetime string."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def render_closed_tickets_tab() -> None:
    """Render completed tickets with search and filters."""
    st.subheader("Tareas cerradas")

    try:
        tickets = [ticket for ticket in load_tickets() if ticket["status"] == CLOSED_STATUS]
        users = load_users()
        companies = load_companies()
    except Exception as exc:
        st.error(f"No se pudieron cargar tareas cerradas: {exc}")
        return

    users_by_id = {user["id"]: user["username"] for user in users}
    companies_by_id = {company["id"]: company for company in companies}

    filter_columns = st.columns(4)
    search = filter_columns[0].text_input("Buscar", placeholder="Titulo o descripcion").strip().lower()
    user_options = ["Todos"] + sorted(
        {users_by_id.get(ticket.get("assigned_user_id"), ticket.get("assigned_to") or "Sin asignar") for ticket in tickets},
    )
    selected_user = filter_columns[1].selectbox("Persona", options=user_options)
    company_options = ["Todas"] + sorted(
        {companies_by_id.get(ticket["company_id"], {}).get("code", f"#{ticket['company_id']}") for ticket in tickets},
    )
    selected_company = filter_columns[2].selectbox("Empresa", options=company_options)
    selected_priority = filter_columns[3].selectbox("Prioridad", options=["Todas", *TICKET_PRIORITIES])

    date_columns = st.columns(2)
    start_date = date_columns[0].date_input("Desde", value=None)
    end_date = date_columns[1].date_input("Hasta", value=None)

    filtered_tickets = []
    for ticket in tickets:
        assignee = users_by_id.get(ticket.get("assigned_user_id"), ticket.get("assigned_to") or "Sin asignar")
        company_code = companies_by_id.get(ticket["company_id"], {}).get("code", f"#{ticket['company_id']}")
        created_date = parse_api_datetime(ticket["created_at"]).date()
        searchable_text = f"{ticket['title']} {ticket['description']}".lower()

        if search and search not in searchable_text:
            continue
        if selected_user != "Todos" and assignee != selected_user:
            continue
        if selected_company != "Todas" and company_code != selected_company:
            continue
        if selected_priority != "Todas" and ticket["priority"] != selected_priority:
            continue
        if start_date and created_date < start_date:
            continue
        if end_date and created_date > end_date:
            continue
        filtered_tickets.append((ticket, assignee, company_code))

    st.caption(f"{len(filtered_tickets)} tareas cerradas")
    if not filtered_tickets:
        st.info("No hay tareas cerradas con esos filtros.")
        return

    card_columns = st.columns(3)
    for index, (ticket, assignee, company_code) in enumerate(filtered_tickets):
        with card_columns[index % 3].container(border=True):
            st.markdown(f"**#{ticket['id']} {ticket['title']}**")
            st.caption(f"{company_code} | {ticket['type']} | {ticket['priority']}")
            st.write(f"Asignado: {assignee}")
            st.write(f"Creada: {parse_api_datetime(ticket['created_at']).date().isoformat()}")
            with st.expander("Descripcion"):
                st.write(ticket["description"])


def render_users_tab(can_manage: bool) -> None:
    """Render user list and management form."""
    if not can_manage:
        return

    st.subheader("Usuarios")

    try:
        users = load_users()
        companies = load_companies()
    except Exception as exc:
        st.error(f"No se pudieron cargar usuarios: {exc}")
        return

    companies_by_id = {company["id"]: company for company in companies}
    user_rows = []
    for user in users:
        ordered_priorities = sorted(user["company_priorities"], key=lambda item: item["priority_order"])
        priority_codes = [
            companies_by_id.get(priority["company_id"], {}).get("code", f"#{priority['company_id']}")
            for priority in ordered_priorities
        ]
        user_rows.append(
            {
                "usuario": user["username"],
                "nombre": user["full_name"],
                "rol": user["role"],
                "nivel": user["skill_level"],
                "activo": user["is_active"],
                "prioridades_empresas": " > ".join(priority_codes) if priority_codes else "-",
                "creado": user["created_at"],
            },
        )

    st.dataframe(user_rows, use_container_width=True, hide_index=True)

    with st.expander("Crear usuario"):
        with st.form("create_user_form", clear_on_submit=True):
            username = st.text_input("Usuario", placeholder="nuevo_usuario")
            password = st.text_input("Password", type="password")
            full_name = st.text_input("Nombre completo", placeholder="Nuevo Usuario")
            role = st.selectbox("Rol", options=["member", "admin"])
            skill_level = st.selectbox("Nivel", options=USER_SKILL_LEVELS, index=1)
            is_active = st.checkbox("Activo", value=True)

            priority_payload: list[dict[str, int]] = []
            if companies:
                company_labels = {f"{company['name']} ({company['code']})": company["id"] for company in companies}
                selected_companies = st.multiselect("Empresas asignadas por prioridad", options=list(company_labels))
                priority_payload = [
                    {"company_id": company_labels[label], "priority_order": index}
                    for index, label in enumerate(selected_companies, start=1)
                ]

            submitted = st.form_submit_button("Crear usuario")

        if submitted:
            try:
                api_request(
                    "POST",
                    "/users",
                    json={
                        "username": username,
                        "password": password,
                        "full_name": full_name or None,
                        "role": role,
                        "skill_level": skill_level,
                        "is_active": is_active,
                        "company_priorities": priority_payload,
                    },
                )
            except Exception as exc:
                st.error(f"No se pudo crear el usuario: {exc}")
            else:
                st.success("Usuario creado correctamente.")
                st.rerun()

    if users:
        with st.expander("Editar usuario"):
            user_options = {user["username"]: user for user in users}
            selected_username = st.selectbox("Usuario", options=list(user_options), key="edit_user_select")
            selected_user = user_options[selected_username]
            selected_user_id = selected_user["id"]
            current_priority_ids = [
                priority["company_id"]
                for priority in sorted(selected_user["company_priorities"], key=lambda item: item["priority_order"])
            ]
            company_labels = {f"{company['name']} ({company['code']})": company["id"] for company in companies}
            labels_by_company_id = {company_id: label for label, company_id in company_labels.items()}
            default_priority_labels = [
                labels_by_company_id[company_id]
                for company_id in current_priority_ids
                if company_id in labels_by_company_id
            ]

            with st.form("edit_user_form"):
                username = st.text_input(
                    "Usuario",
                    value=selected_user["username"],
                    key=f"edit_username_{selected_user_id}",
                )
                full_name = st.text_input(
                    "Nombre completo",
                    value=selected_user["full_name"] or "",
                    key=f"edit_full_name_{selected_user_id}",
                )
                role = st.selectbox(
                    "Rol",
                    options=["member", "admin"],
                    index=["member", "admin"].index(selected_user["role"]),
                    key=f"edit_role_{selected_user_id}",
                )
                skill_level = st.selectbox(
                    "Nivel",
                    options=USER_SKILL_LEVELS,
                    index=USER_SKILL_LEVELS.index(selected_user["skill_level"]),
                    key=f"edit_skill_level_{selected_user_id}",
                )
                is_active = st.checkbox(
                    "Activo",
                    value=selected_user["is_active"],
                    key=f"edit_is_active_{selected_user_id}",
                )
                new_password = st.text_input(
                    "Nueva password",
                    type="password",
                    help="Dejalo vacio para mantener la password actual.",
                    key=f"edit_password_{selected_user_id}",
                )
                selected_companies = st.multiselect(
                    "Empresas asignadas por prioridad",
                    options=list(company_labels),
                    default=default_priority_labels,
                    key=f"edit_priorities_{selected_user_id}",
                )
                submitted = st.form_submit_button("Guardar cambios")

            if submitted:
                payload: dict[str, Any] = {
                    "username": username,
                    "full_name": full_name or None,
                    "role": role,
                    "skill_level": skill_level,
                    "is_active": is_active,
                    "company_priorities": [
                        {"company_id": company_labels[label], "priority_order": index}
                        for index, label in enumerate(selected_companies, start=1)
                    ],
                }
                if new_password:
                    payload["password"] = new_password

                try:
                    updated_user = api_request("PUT", f"/users/{selected_user['id']}", json=payload)
                except Exception as exc:
                    st.error(f"No se pudo editar el usuario: {exc}")
                else:
                    if updated_user["id"] == st.session_state["current_user"]["id"]:
                        st.session_state["current_user"] = updated_user
                    st.success("Usuario actualizado correctamente.")
                    st.rerun()

        with st.expander("Eliminar usuario"):
            user_options = {user["username"]: user["id"] for user in users}
            selected_user = st.selectbox("Usuario", options=list(user_options), key="delete_user_select")
            if st.button("Eliminar usuario", type="secondary"):
                try:
                    api_request("DELETE", f"/users/{user_options[selected_user]}")
                except Exception as exc:
                    st.error(f"No se pudo eliminar el usuario: {exc}")
                else:
                    st.success("Usuario eliminado.")
                    st.rerun()


def main() -> None:
    """Render the Streamlit application."""
    if "access_token" not in st.session_state or "current_user" not in st.session_state:
        render_login()
        return

    st.set_page_config(page_title="AI SmartEC Tickets", layout="wide")
    st.title("AI SmartEC Tickets")
    st.caption("Panel tipo Jira para gestionar tickets tecnicos, asignaciones y analisis de impacto.")

    render_status()
    can_manage = is_admin()

    tab_names = ["Tablero", "Tareas cerradas", "Crear ticket", "Empresas"]
    if can_manage:
        tab_names.append("Admin usuarios")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        render_board_tab(can_manage)
    with tabs[1]:
        render_closed_tickets_tab()
    with tabs[2]:
        render_tickets_tab()
    with tabs[3]:
        render_companies_tab(can_manage)
    if can_manage:
        with tabs[4]:
            render_users_tab(can_manage)


if __name__ == "__main__":
    main()
