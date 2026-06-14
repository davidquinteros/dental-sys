# 🦷 DentalSys — Sistema de Gestión de Clínica Dental

Sistema MVP completo para gestión de clínica dental con módulos de **Usuarios**, **Pacientes**, **Citas**, **Atenciones Clínicas**, **Cobros** y **Dashboard**.

---

## 🏗️ Arquitectura del Sistema

```
dental-clinic/
├── backend/                    # Flask (Python)
│   ├── app/
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── user.py         # Usuarios y roles
│   │   │   ├── patient.py      # Pacientes
│   │   │   ├── appointment.py  # Citas
│   │   │   ├── treatment.py    # Atenciones y planes
│   │   │   └── billing.py      # Facturas y cobros
│   │   ├── routes/             # API REST endpoints
│   │   │   ├── auth.py         # Login, JWT, perfil
│   │   │   ├── users.py        # CRUD usuarios
│   │   │   ├── patients.py     # CRUD pacientes + historial
│   │   │   ├── appointments.py # Citas + disponibilidad
│   │   │   ├── treatments.py   # Atenciones + planes
│   │   │   ├── billing.py      # Facturas + pagos + planes de pago
│   │   │   └── dashboard.py    # Métricas del dashboard
│   │   └── middleware/
│   │       └── auth.py         # JWT decorators + RBAC
│   ├── run.py                  # Punto de entrada Flask
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/                   # Angular 18 (Standalone)
    └── src/app/
        ├── core/
        │   ├── models/         # TypeScript interfaces
        │   ├── services/       # AuthService + API services
        │   ├── guards/         # Auth guard + Role guard
        │   └── interceptors/   # JWT interceptor con auto-refresh
        ├── shared/
        │   └── components/
        │       └── layout/     # Shell con sidebar navegación
        └── features/
            ├── auth/           # Login
            ├── dashboard/      # Dashboard con métricas
            ├── patients/       # Listado, detalle, formulario
            ├── appointments/   # Listado + agenda + formulario
            ├── treatments/     # Atenciones + planes de tratamiento
            ├── billing/        # Facturas + cobros + planes de pago
            └── users/          # Gestión de usuarios (admin)
```

---

## 🚀 Instalación y Configuración

### Prerrequisitos
- Python 3.11+
- PostgreSQL 14+
- Node.js 18+
- Angular CLI 18: `npm install -g @angular/cli`

### Setup automático
```bash
bash setup.sh
```

### Setup manual

#### 1. Base de datos PostgreSQL
```sql
CREATE DATABASE dental_clinic_db;
CREATE USER dental_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dental_clinic_db TO dental_user;
```

#### 2. Backend Flask
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
cp .env.example .env
# Edite .env con sus credenciales de base de datos

# Migraciones
flask db init
flask db migrate -m "initial migration"
flask db upgrade

# Datos iniciales
flask seed

# Iniciar servidor
flask run --port 5000
```

#### 3. Frontend Angular
```bash
cd frontend
npm install
npm start                          # http://localhost:4200
```

---

## 🔐 Roles y Permisos

| Funcionalidad | Admin | Médico | Recepcionista | Asistente |
|---|:---:|:---:|:---:|:---:|
| Dashboard | ✅ | ✅ | ✅ | ✅ |
| Gestión de Usuarios | ✅ | ❌ | ❌ | ❌ |
| Pacientes (CRUD) | ✅ | ✅ | ✅ | ✅ |
| Citas (todas) | ✅ | Solo propias | ✅ | Solo asignadas |
| Atenciones clínicas | ✅ | ✅ | ❌ | ✅ |
| Planes de tratamiento | ✅ | ✅ | ❌ | ✅ |
| Cobros y Facturas | ✅ | ❌ | ✅ | ❌ |
| Planes de Pago | ✅ | ❌ | ✅ | ❌ |

---

## 📡 API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/auth/login` | Iniciar sesión |
| POST | `/api/auth/refresh` | Renovar token JWT |
| GET | `/api/auth/me` | Perfil del usuario logueado |
| PUT | `/api/auth/change-password` | Cambiar contraseña |

### Usuarios
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/users/` | Listar usuarios |
| POST | `/api/users/` | Crear usuario (admin) |
| PUT | `/api/users/:id` | Actualizar usuario |
| DELETE | `/api/users/:id` | Desactivar usuario (admin) |
| GET | `/api/users/doctors` | Lista de médicos activos |

### Pacientes
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/patients/` | Listar con búsqueda y paginación |
| POST | `/api/patients/` | Crear paciente |
| GET | `/api/patients/:id` | Detalle de paciente |
| PUT | `/api/patients/:id` | Actualizar paciente |
| GET | `/api/patients/:id/history` | Historial completo |

### Citas
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/appointments/` | Listar con filtros |
| POST | `/api/appointments/` | Crear cita |
| PUT | `/api/appointments/:id` | Actualizar/cambiar estado |
| POST | `/api/appointments/:id/cancel` | Cancelar cita |
| GET | `/api/appointments/availability` | Verificar disponibilidad médico |
| GET | `/api/appointments/today` | Citas del día actual |

### Atenciones
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/treatments/` | Listar atenciones |
| POST | `/api/treatments/` | Registrar atención |
| PUT | `/api/treatments/:id` | Actualizar atención |
| GET | `/api/treatments/plans` | Listar planes |
| POST | `/api/treatments/plans` | Crear plan de tratamiento |
| PUT | `/api/treatments/plans/:id` | Actualizar plan |

### Cobros
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/billing/invoices` | Listar facturas |
| POST | `/api/billing/invoices` | Crear factura |
| GET | `/api/billing/invoices/:id` | Detalle factura |
| POST | `/api/billing/invoices/:id/payments` | Registrar pago |
| GET | `/api/billing/payment-plans` | Listar planes de pago |
| POST | `/api/billing/payment-plans` | Crear plan de pago |
| POST | `/api/billing/payment-plans/:id/installment` | Registrar cuota |
| GET | `/api/billing/summary` | Resumen financiero |

### Dashboard
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/dashboard/` | Métricas y resumen del día |

---

## 🔑 Credenciales de Prueba (después de `flask seed`)

| Rol | Email | Contraseña |
|---|---|---|
| Administrador | admin@clinica.com | Admin2025! |
| Médico | dr.garcia@clinica.com | Doctor2025! |
| Médico | dr.morales@clinica.com | Doctor2025! |
| Recepcionista | recepcion@clinica.com | Recep2025! |
| Asistente | asistente@clinica.com | Asist2025! |

---

## 🗺️ Próximas Entregas (Roadmap)

### Entregable 2
- [ ] Notificaciones por email/SMS para citas
- [ ] Exportación de reportes en PDF/Excel
- [ ] Módulo de inventario de materiales
- [ ] Calendario visual de citas (vista semanal/mensual)

### Entregable 3
- [ ] Odontograma interactivo (mapa dental completo)
- [ ] Subida de radiografías e imágenes clínicas
- [ ] Portal del paciente (acceso limitado)
- [ ] Módulo de recordatorios automáticos

### Entregable 4
- [ ] Reportes analíticos avanzados
- [ ] Integración con sistemas de pago (QR, etc.)
- [ ] App móvil (Angular PWA)
- [ ] Multi-consultorio / multi-sede

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend Framework | Flask 3.1 (Python) |
| ORM | SQLAlchemy + Flask-Migrate (Alembic) |
| Auth | Flask-JWT-Extended (JWT tokens) |
| CORS | Flask-CORS |
| Hashing | Flask-Bcrypt |
| Base de Datos | PostgreSQL |
| Frontend | Angular 18 (Standalone Components) |
| State Management | Angular Signals |
| Routing | Angular Router (Lazy Loading) |
| HTTP | HttpClient + Interceptors |
| Formularios | Reactive Forms |
