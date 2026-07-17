# 🦷 DentalSys — Plataforma SaaS Multi-Tenant para Clínicas Dentales

Sistema SaaS multi-tenant para gestión de clínicas dentales: **Pacientes**, **Citas** (calendario visual), **Atenciones Clínicas** (con odontograma y recetario estructurado), **Cobros** (facturas y planes de pago), y una capa de administración de la plataforma para dar de alta clínicas y gestionar sus suscripciones.

Cada clínica es un tenant aislado (datos, usuarios, permisos, configuración) dentro de la misma base de datos compartida, reforzado por dos capas de seguridad independientes (filtro a nivel de ORM + Row Level Security de Postgres — ver [Multi-tenancy y seguridad](#-multi-tenancy-y-seguridad)).

> Para guía técnica exhaustiva orientada a quien desarrolla sobre este código (incluyendo gotchas, decisiones de diseño y el detalle interno de cada subsistema), ver [`CLAUDE.md`](CLAUDE.md) — este README es la introducción general al proyecto.

---

## 🏗️ Arquitectura del Sistema

Un backend Flask sirve a **dos** aplicaciones Angular 18 independientes:

- **`frontend/`** (puerto 4200) — la app que usa el personal de cada clínica (recepción, médicos, asistentes, admin de la clínica). Todo su acceso está acotado a los datos de su propia clínica.
- **`admin-frontend/`** (puerto 4300) — una app separada, mucho más chica, usada únicamente por el operador de la plataforma (el dueño del SaaS) para dar de alta clínicas, gestionar sus planes de suscripción y cobros. No comparte código ni estado con `frontend/`.

```
dental-clinic/
├── backend/                       # Flask (Python) + PostgreSQL (Supabase)
│   ├── app/
│   │   ├── models/
│   │   │   ├── clinic.py          # Clinic (tenant + estado de suscripción)
│   │   │   ├── subscription.py    # SubscriptionTier, SubscriptionPayment
│   │   │   ├── user.py            # Usuarios y roles
│   │   │   ├── patient.py         # Pacientes (medical_history/odontogram como JSON)
│   │   │   ├── appointment.py     # Citas
│   │   │   ├── appointment_type.py
│   │   │   ├── consultorio.py     # Consultorios/salas
│   │   │   ├── treatment.py       # Atenciones, planes de tratamiento, recetario
│   │   │   ├── treatment_image.py # Fotos clínicas (Supabase Storage)
│   │   │   ├── billing.py         # Facturas, ítems, pagos, planes de pago
│   │   │   └── permission.py      # Page + RolePermission (permisos por clínica)
│   │   ├── routes/                # Un blueprint por dominio, bajo /api/<nombre>
│   │   │   ├── auth.py, users.py, patients.py, appointments.py
│   │   │   ├── treatments.py, billing.py, dashboard.py
│   │   │   ├── consultorios.py, appointment_types.py, permissions.py
│   │   │   ├── clinic.py          # Info/logo propios de la clínica (self-service)
│   │   │   └── platform_admin.py  # /api/platform/* — solo el operador SaaS
│   │   ├── middleware/
│   │   │   ├── auth.py            # JWT + decoradores de rol (incluye platform_admin_required)
│   │   │   └── tenancy.py         # Filtro ORM por clinic_id + GUCs de RLS
│   │   └── utils/
│   │       ├── seeder.py          # flask seed / create-clinic / create-platform-admin
│   │       ├── storage.py         # Supabase Storage (fotos clínicas, logos)
│   │       ├── serialization.py   # iso_utc() — timestamps UTC consistentes
│   │       └── clinic_time.py     # Hora local de la clínica (agenda)
│   ├── migrations/versions/       # Alembic — incluye las migraciones de RLS
│   ├── run.py
│   └── requirements.txt
│
├── frontend/                      # Angular 18 (Standalone) — personal de clínica
│   └── src/app/
│       ├── core/                  # guards (auth/rol), services, interceptors, util (fechas)
│       ├── shared/                # layout, print-clinic-header, print-document.css
│       └── features/
│           ├── auth/, dashboard/, patients/ (+ odontograma, historia médica, impresión)
│           ├── appointments/, calendar/ (agenda visual), planes/
│           ├── treatments/ (+ recetario imprimible), billing/
│           ├── users/, permissions/, consultorios/, appointment-types/
│
└── admin-frontend/                 # Angular 18 (Standalone) — operador de la plataforma
    └── src/app/features/
        ├── auth/, dashboard/, clinics/, subscription-tiers/
```

---

## 🔒 Multi-tenancy y seguridad

Cada tabla de datos de una clínica (`patients`, `appointments`, `treatments`, `invoices`, etc.) tiene una columna `clinic_id`. El aislamiento entre clínicas se refuerza por **dos capas independientes**, deliberadamente redundantes:

1. **Filtro a nivel de ORM** — un evento de SQLAlchemy inyecta `clinic_id == <clínica del usuario>` en cada consulta, incluso en relaciones cargadas de forma perezosa.
2. **Row Level Security de Postgres** — políticas RLS en la base de datos misma, como defensa adicional ante cualquier código que use SQL crudo.

Una clínica cuyo `usuario` pertenece a ella nunca puede leer ni escribir datos de otra, aunque una de las dos capas fallara. Por encima de esto hay dos sistemas de autorización separados:

- **Roles** (`admin`, `doctor`, `receptionist`, `assistant`) — gatean endpoints completos.
- **Permisos por página** — cada clínica puede personalizar, desde su propio panel de administración, qué rol puede ver/crear/editar/eliminar cada sección de la app (módulo de Permisos).

Y un tercer nivel, totalmente separado de lo anterior: el **operador de la plataforma** (quien vende el SaaS) opera desde `admin-frontend/` con acceso no acotado a ninguna clínica en particular, para darlas de alta y gestionar su suscripción/facturación.

---

## 🚀 Instalación y Configuración

### Opción recomendada: Docker Compose

```bash
docker compose up -d --build
```

Levanta backend (`:5000`), `frontend/` (`:4200`) y `admin-frontend/` (`:4300`) juntos. Requiere un archivo `.env` en la raíz con `DATABASE_URL`/`MIGRATIONS_DATABASE_URL` apuntando a un Postgres (ver más abajo) — no incluye un contenedor de base de datos propio por defecto.

Dos variantes para redes restringidas (proxies corporativos — detalle completo en `CLAUDE.md`, sección "Restricted/corporate networks"):

- **Postgres local opcional**: `docker compose --profile localdb up -d` agrega un contenedor `db` para desarrollar donde un Postgres externo es inalcanzable (p. ej. puerto 5432 saliente bloqueado). Requiere apuntar el `.env` al servicio `db` y bootstrapear la base una vez (`init_db.py` + `flask db stamp head` con el rol de migraciones, luego `flask seed`).
- **Imágenes de frontend pre-construidas**: si `registry.npmjs.org` está bloqueado, `.github/workflows/build-images.yml` construye las imágenes en GitHub Actions y las publica en GHCR; en la máquina restringida basta `docker compose pull frontend admin-frontend` y `docker compose up -d` (sin `--build`).

```bash
docker compose exec backend flask db upgrade                # aplicar migraciones
docker compose exec backend flask seed                      # datos de demo (clínica #1)
docker compose exec backend flask create-clinic --name "..." --admin-email "..." --admin-password "..."
docker compose exec backend flask create-platform-admin --email "..." --password "..."   # usuario del operador SaaS
```

### Opción manual (sin Docker)

#### 1. Base de datos PostgreSQL
```sql
CREATE DATABASE dental_clinic_db;
CREATE USER dental_app WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dental_clinic_db TO dental_app;
```
(La app también soporta Postgres administrado, p. ej. Supabase — ver `create_app_role.sql` para el esquema de dos roles, uno restringido para runtime y otro dueño del esquema para migraciones.)

#### 2. Backend Flask
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env
# Editar .env con las credenciales de base de datos

flask db upgrade
flask seed
flask run --port 5000
```

#### 3. Frontend Angular
```bash
cd frontend
npm install
npm start                          # http://localhost:4200

cd ../admin-frontend
npm install
npm start                          # http://localhost:4300
```

---

## 🔐 Roles y Permisos

La matriz por defecto (personalizable por cada clínica desde el módulo de Permisos):

| Funcionalidad | Admin | Médico | Recepcionista | Asistente |
|---|:---:|:---:|:---:|:---:|
| Dashboard | ✅ | ✅ | ✅ | ✅ |
| Gestión de Usuarios | ✅ | ❌ | ❌ | ❌ |
| Pacientes (CRUD) | ✅ | ✅ | ✅ | ✅ |
| Citas (todas) | ✅ | Solo propias | ✅ | Solo asignadas |
| Calendario visual | ✅ | ✅ | ✅ | ✅ |
| Atenciones clínicas (+ recetario, fotos) | ✅ | ✅ | ❌ | ✅ |
| Planes de tratamiento | ✅ | ✅ | ❌ | ✅ |
| Cobros, Facturas y Planes de Pago | ✅ | ❌ | ✅ | ❌ |
| Consultorios / Tipos de cita | ✅ | ❌ | ❌ | ❌ |
| Permisos (configurar la matriz) | ✅ | ❌ | ❌ | ❌ |

---

## 📡 API Endpoints

Todas las rutas viven bajo `/api/<blueprint>` en el backend Flask; la documentación interactiva completa (Swagger/OpenAPI) está en **`/api/docs/`**.

### Autenticación — `/api/auth`
`POST /login` · `POST /refresh` · `GET /me` · `PUT /change-password`

### Usuarios — `/api/users`
`GET /` · `POST /` (admin) · `PUT /:id` · `DELETE /:id` (desactivar) · `GET /doctors`

### Pacientes — `/api/patients`
`GET /` (búsqueda + paginación) · `POST /` · `GET /:id` · `PUT /:id` · `GET /:id/history` · odontograma e historia médica vía el mismo recurso (`medical_history`/`odontogram`, JSON)

### Citas — `/api/appointments`
`GET /` · `POST /` · `PUT /:id` · `POST /:id/cancel` · `GET /availability` · `GET /today`

### Atenciones y planes de tratamiento — `/api/treatments`
`GET /` · `POST /` · `PUT /:id` · `GET /plans` · `POST /plans` · `PUT /plans/:id` — más fotos clínicas: `POST/GET /:id/images`, `POST/GET /plans/:id/images`, `GET /images/:id/file`, `DELETE /images/:id`

### Cobros — `/api/billing`
`GET/POST /invoices` · `GET /invoices/:id` · `POST /invoices/:id/payments` · `GET/POST /payment-plans` · `POST /payment-plans/:id/installment` · `GET /payment-plans/:id/installments` · `GET /summary`

### Configuración de la clínica — `/api/consultorios`, `/api/appointment-types`, `/api/permissions`, `/api/clinic`
CRUD de consultorios y tipos de cita · matriz de permisos por rol (`GET/PUT /permissions/matrix`, `GET /permissions/me`) · datos propios de la clínica para encabezados impresos (`GET /clinic/info`, `GET /clinic/logo`)

### Dashboard — `/api/dashboard`
`GET /` — métricas y resumen del día

### Plataforma (solo operador SaaS, `admin-frontend`) — `/api/platform`
`GET /dashboard` · `GET/POST /clinics` · `GET/PUT /clinics/:id` · `POST/GET /clinics/:id/logo` · `POST /clinics/:id/reset-admin-password` · `GET/POST/PUT /subscription-tiers` · `GET/POST /clinics/:id/payments`

---

## 🔑 Credenciales de Prueba (después de `flask seed`)

Datos de demo para la clínica #1, solo en un entorno local/testing recién sembrado:

| Rol | Email | Contraseña |
|---|---|---|
| Administrador | admin@clinica.com | Admin2025! |
| Médico | dr.garcia@clinica.com | Doctor2025! |
| Médico | dr.morales@clinica.com | Doctor2025! |
| Recepcionista | recepcion@clinica.com | Recep2025! |
| Asistente | asistente@clinica.com | Asist2025! |

---

## ✅ Funcionalidades implementadas

- **Multi-tenancy SaaS completo**: alta de clínicas, períodos de prueba, estados de suscripción (`trial`/`active`/`past_due`/`suspended`/`cancelled`), bloqueo de acceso automático al vencer el plan.
- **Calendario visual de citas** (vista semanal/mensual), con colores por médico y disponibilidad de médico/consultorio en tiempo real.
- **Odontograma interactivo** (mapa dental completo, por pieza FDI) y su versión estática imprimible.
- **Recetario estructurado**: lista de medicamentos (nombre, concentración, forma, dosis, duración, indicaciones) con vista imprimible dedicada.
- **Impresión de historia médica** del paciente (antecedentes, odontograma, historial de atenciones) en un documento único.
- **Subida de fotos clínicas** y de logo de clínica, en un bucket privado de Supabase Storage servido solo vía endpoints autenticados.
- **Multi-consultorio / multi-sede** dentro de cada clínica, con tipos de cita configurables.
- **Permisos configurables por clínica** (qué rol ve/edita cada sección), además de los roles base.
- **Planes de pago en cuotas** (montos variables, historial de pagos) además de facturación de pago único.

## 🗺️ Próximas Entregas (Roadmap)

- [ ] Notificaciones por email/SMS para citas
- [ ] Exportación de reportes en PDF/Excel desde el dashboard
- [ ] Módulo de inventario de materiales
- [ ] Portal del paciente (acceso limitado, fuera de `frontend`/`admin-frontend`)
- [ ] Módulo de recordatorios automáticos
- [ ] Reportes analíticos avanzados
- [ ] Integración con pasarelas de pago (más allá del registro manual de cobro en efectivo/QR)
- [ ] App móvil (Angular PWA)
- [ ] Página de auto-configuración de clínica dentro de `frontend/` (hoy esos datos solo se editan desde `admin-frontend`)

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend Framework | Flask 3.1 (Python) |
| ORM | SQLAlchemy + Flask-Migrate (Alembic) |
| Auth | Flask-JWT-Extended (JWT tokens) |
| CORS | Flask-CORS |
| Hashing | Flask-Bcrypt |
| Base de Datos | PostgreSQL, alojado en Supabase (con Row Level Security) |
| Almacenamiento de archivos | Supabase Storage (bucket privado — fotos clínicas, logos) |
| Frontend | Angular 18 (Standalone Components) — dos apps: `frontend/` y `admin-frontend/` |
| State Management | Angular Signals |
| Routing | Angular Router (Lazy Loading) |
| HTTP | HttpClient + Interceptors |
| Formularios | Reactive Forms |
| Hosting | Render (backend + dos Static Sites por app), entornos separados para `main` (producción) y `testing` |
