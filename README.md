# AI SmartEC Tickets

Backend MVP profesional para gestionar tickets tecnicos de empresas electricas y analizar automaticamente el impacto probable en un repositorio Python.

La aplicacion esta pensada como un Jira tecnico interno para equipos de Union Fenosa, Iberdrola, TAQA, Areti y EDP.

## Stack Tecnico

- Python 3.12
- FastAPI
- PostgreSQL 16 con pgvector
- SQLAlchemy 2 async
- Alembic
- Pydantic v2
- Redis
- Celery
- Docker y Docker Compose
- Streamlit
- Pytest
- Ruff
- GitHub Actions

No incluye React, Django, Kubernetes ni microservicios complejos.

## Estructura

```text
app/
  main.py
  api/routes/
  core/config.py
  db/
    session.py
    base.py
    models/
  schemas/
  services/
  workers/
frontend/
  streamlit_app.py
tests/
alembic/
```

## Arranque Rapido

1. Crea `.env` a partir del ejemplo:

```bash
cp .env.example .env
```

2. Levanta el stack completo:

```bash
docker compose up --build
```

El servicio `api` ejecuta `alembic upgrade head` antes de arrancar FastAPI.

Servicios:

- API: `http://localhost:8000`
- Demo Streamlit: `http://localhost:8501`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Para ejecutar en segundo plano:

```bash
docker compose up --build -d
```

Para parar:

```bash
docker compose down
```

Para parar y borrar volumen de PostgreSQL:

```bash
docker compose down -v
```

## Variables de Entorno

El proyecto usa `pydantic-settings` y carga `.env`.

Variables principales:

```env
APP_NAME="AI SmartEC Tickets"
APP_VERSION="0.1.0"
ENVIRONMENT="local"

POSTGRES_USER="smartec"
POSTGRES_PASSWORD="change-me"
POSTGRES_DB="ai_smartec_tickets"
POSTGRES_HOST="postgres"
POSTGRES_PORT="5432"
DATABASE_URL="postgresql+asyncpg://smartec:change-me@postgres:5432/ai_smartec_tickets"

REDIS_URL="redis://redis:6379/0"
CELERY_BROKER_URL="redis://redis:6379/0"
CELERY_RESULT_BACKEND="redis://redis:6379/0"

AI_PROVIDER="mock"
AI_API_KEY=""
AI_MODEL="gpt-4.1"
AI_API_BASE_URL="https://api.openai.com/v1"
AI_TIMEOUT_SECONDS="90"

API_BASE_URL="http://api:8000"
PUBLIC_API_BASE_URL="http://localhost:8000"

AUTH_SECRET_KEY="change-this-local-secret"
ACCESS_TOKEN_EXPIRE_MINUTES="480"
CORS_ORIGINS='["http://localhost:8501","http://127.0.0.1:8501"]'
```

No se versiona `.env`. Solo se versiona `.env.example`.

`API_BASE_URL` lo usa Streamlit en servidor para llamar a FastAPI. Dentro de Docker debe apuntar a `http://api:8000`. Si ejecutas Streamlit fuera de Docker, usa `http://localhost:8000`.

`PUBLIC_API_BASE_URL` lo usa el tablero drag/drop embebido en el navegador. En Docker debe apuntar a `http://localhost:8000` porque esa llamada sale desde tu navegador, no desde el contenedor.

`AUTH_SECRET_KEY` firma los tokens de sesion. Cambialo en cualquier entorno compartido.

## Migraciones

Aplicar migraciones:

```bash
docker compose exec api alembic upgrade head
```

Crear una migracion nueva:

```bash
docker compose exec api alembic revision --autogenerate -m "describe change"
```

La migracion inicial crea:

- extension PostgreSQL `vector`
- `companies`
- `tickets`
- `ticket_analyses`
- enums PostgreSQL para tipo, estado y prioridad

La segunda migracion crea usuarios, prioridades de empresa por usuario, rama de repositorio por empresa y actualiza los tipos de ticket.

## Endpoints

- `GET /health`
- `POST /auth/login`
- `POST /companies`
- `GET /companies`
- `GET /companies/{company_id}`
- `PUT /companies/{company_id}`
- `DELETE /companies/{company_id}`
- `POST /users`
- `GET /users`
- `GET /users/{user_id}`
- `PUT /users/{user_id}`
- `DELETE /users/{user_id}`
- `POST /tickets`
- `GET /tickets`
- `GET /tickets/{ticket_id}`
- `PUT /tickets/{ticket_id}`
- `DELETE /tickets/{ticket_id}`
- `POST /tickets/{ticket_id}/analyze`

## Demo Streamlit

El proyecto incluye una interfaz grafica sencilla en `frontend/streamlit_app.py`.

Con Docker:

```bash
docker compose up --build
```

Abre:

```text
http://localhost:8501
```

La demo funciona como panel tipo Jira interno y permite:

- login real contra `POST /auth/login`
- logout desde la barra lateral
- ver un tablero por estados (`pendiente`, `en_curso`, `pruebas_internas`, `validacion`, `desplegado`)
- mover tareas a `cierre`; al cerrarlas salen del tablero principal y aparecen en `Tareas cerradas`
- consultar `Tareas cerradas` con buscador y filtros por persona, empresa, prioridad y fecha
- mover tickets entre fases arrastrando tarjetas con el raton
- abrir cada ticket con doble click para editarlo y ver su analisis/propuesta
- ver empresas
- crear empresas con rama de repositorio asociada
- eliminar empresas solo con rol `admin`
- ver y crear usuarios
- eliminar usuarios solo con rol `admin`
- eliminar tareas solo con rol `admin`
- asignar prioridades de empresas a cada usuario
- ver tickets
- crear tickets de tipo `historia_usuario`, `tarea`, `incidencia` o `bug`
- asignar tickets a usuarios activos o dejar asignacion automatica
- generar automaticamente asignacion, estimacion de horas y propuesta de solucion al crear un ticket
- ver dentro de cada tarea la complejidad, horas estimadas, archivos afectados, riesgos, tareas recomendadas y propuesta IA

Usuarios iniciales:

- `admin/admin`, rol `admin`
- `Sergio/sergio`, rol `admin`
- `Ignacio/ignacio`, rol `member`

Para ejecutar Streamlit localmente fuera de Docker:

```bash
pip install -e ".[dev]"
set API_BASE_URL=http://localhost:8000
streamlit run frontend/streamlit_app.py
```

En PowerShell:

```powershell
$env:API_BASE_URL="http://localhost:8000"
streamlit run frontend/streamlit_app.py
```

## Ejemplos Curl

Healthcheck:

```bash
curl http://localhost:8000/health
```

Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Guardar token para endpoints de administracion:

```bash
TOKEN="pega_aqui_el_access_token"
```

Crear empresa:

```bash
curl -X POST http://localhost:8000/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Iberdrola",
    "code": "IBE",
    "description": "Empresa electrica para pruebas del MVP.",
    "repo_url": "https://github.com/moisefi/Serisa_Control_Fichajes.git",
    "repo_branch": "feature/iberdrola"
  }'
```

Listar empresas:

```bash
curl http://localhost:8000/companies
```

Listar usuarios:

```bash
curl http://localhost:8000/users
```

Crear usuario con prioridad de empresas:

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "demo",
    "password": "demo",
    "full_name": "Usuario Demo",
    "role": "member",
    "company_priorities": [
      { "company_id": 1, "priority_order": 1 }
    ]
  }'
```

Crear ticket:

```bash
curl -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Alta de nuevo suministro",
    "description": "Gestionar validaciones tecnicas para un nuevo punto de suministro.",
    "company_id": 1,
    "type": "historia_usuario",
    "priority": "alta",
    "assigned_user_id": 2
  }'
```

Si omites `assigned_user_id`, el backend asigna automaticamente el ticket al usuario activo mas adecuado segun prioridades de empresa y carga actual. Al crear el ticket tambien se genera el primer analisis de impacto.

Analizar ticket:

```bash
curl -X POST http://localhost:8000/tickets/1/analyze
```

Eliminar ticket como admin:

```bash
curl -X DELETE http://localhost:8000/tickets/1 \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta esperada del analisis:

```json
{
  "id": 1,
  "ticket_id": 1,
  "complexity": "alta",
  "estimated_hours": 28,
  "affected_files": ["app/api/routes/tickets.py"],
  "risks": ["Cambios en validaciones pueden afectar tickets existentes."],
  "technical_summary": "Resumen tecnico simulado...",
  "recommended_tasks": ["Revisar el alcance funcional con operaciones."],
  "proposed_changes": [
    {
      "file": "app/api/routes/tickets.py",
      "branch": "feature/iberdrola",
      "change": "Propuesta de analisis IA..."
    }
  ],
  "created_at": "2026-05-11T10:00:00Z"
}
```

## Desarrollo Local

Instalar dependencias de desarrollo:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Lint:

```bash
ruff check .
```

Tests:

```bash
pytest
```

Los tests usan SQLite en memoria mediante overrides de dependencias FastAPI. No necesitan PostgreSQL ni Redis.

## Docker

`docker-compose.yml` define:

- `api`: FastAPI + Alembic
- `frontend`: Streamlit en `http://localhost:8501`
- `postgres`: PostgreSQL con pgvector
- `redis`: broker/cache
- `worker`: Celery worker preparado para trabajos futuros

La imagen instala dependencias runtime del proyecto. Las dependencias de test/lint se instalan localmente o en CI mediante `.[dev]`.

## GitHub Actions

`.github/workflows/ci.yml` ejecuta en push a `main` y pull requests:

```bash
ruff check .
pytest
```

Usa Python 3.12 y dependencias `.[dev]`.

## Analisis IA y Proveedores Externos

El endpoint `POST /tickets/{ticket_id}/analyze` y la creacion automatica de tickets usan un proveedor configurable.

El punto de extension esta en:

- `app/services/analysis.py`: interfaz `TicketImpactAnalyzer`
- `app/services/ai_provider_analysis.py`: implementacion para proveedores compatibles con Responses API
- `app/services/analyzer_factory.py`: selecciona proveedor local o externo
- `app/services/repository.py`: clona/actualiza repos configurados en cache local

Modo mock, por defecto:

```env
AI_PROVIDER="mock"
AI_API_KEY=""
```

Modo proveedor IA externo:

```env
AI_PROVIDER="openai"
AI_API_KEY="sk-..."
AI_MODEL="gpt-4.1"
AI_API_BASE_URL="https://api.openai.com/v1"
```

La variable `AI_API_BASE_URL` permite apuntar a proveedores compatibles con la misma forma de API.
Para otros proveedores con APIs distintas se debe anadir una clase nueva que implemente `TicketImpactAnalyzer`
y seleccionarla desde `app/services/analyzer_factory.py`.

Despues reinicia:

```bash
docker compose up --build -d
```

No se usa login de Google ni sesion web personal. El backend debe autenticarse con una API key del proveedor elegido.

Cuando una empresa tiene `repo_url` y `repo_branch`, el analizador:

- clona o actualiza la rama en `REPOSITORY_CACHE_DIR`
- lee ficheros candidatos de forma local y de solo lectura
- manda al modelo la descripcion del ticket y fragmentos relevantes de codigo
- devuelve complejidad, horas, riesgos, tareas y propuesta de cambios
- no modifica archivos ni hace push al repositorio

## Notas de Calidad

- SQLAlchemy 2 async con `AsyncSession`.
- Pydantic v2 con `from_attributes=True`.
- Enums persistidos con valores de negocio (`pendiente`, `historia_usuario`, `urgente`).
- Tipos de ticket actuales: `historia_usuario`, `tarea`, `incidencia`, `bug`.
- Usuarios base insertados por migracion: `admin/admin`, `Sergio/sergio`, `Ignacio/ignacio`.
- Roles iniciales: `admin` y `Sergio` son `admin`; `Ignacio` es `member`.
- Login real con token bearer firmado para la demo interna.
- Borrado de empresas, usuarios y tareas protegido en API por rol `admin`.
- `pgvector` queda habilitado para embeddings futuros.
- Errores de unicidad de empresas devuelven `409 Conflict`.
- La capa de analisis esta desacoplada del endpoint.
- Las empresas pueden guardar `repo_url` y `repo_branch`.
- Si una empresa tiene repo configurado, el analisis clona/actualiza esa rama en una cache local de solo lectura,
  detecta archivos candidatos y los muestra en la propuesta sin modificar el repositorio.
- Para probar Serisa usa:
  `repo_url=https://github.com/moisefi/Serisa_Control_Fichajes.git` y `repo_branch=master`.
- Mientras no haya repositorio conectado, la propuesta aparece como `Pendiente de desarrollar`.

## Troubleshooting

Ver logs de API:

```bash
docker compose logs api --tail 100
```

Ver estado de servicios:

```bash
docker compose ps
```

Recrear base desde cero:

```bash
docker compose down -v
docker compose up --build
```
