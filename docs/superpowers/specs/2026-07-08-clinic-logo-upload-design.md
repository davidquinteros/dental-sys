# Subida de Logo de Clínica (bucket privado) — Design Spec

**Fecha:** 2026-07-08
**Estado:** Aprobado

## Contexto

FCLI-11 (recetario estructurado, ya construido) agregó `Clinic.logo_url` como campo de texto libre — el admin pega manualmente una URL externa a una imagen ya alojada en otro lado. El usuario pidió reemplazar esto por una subida de archivo real, reutilizando la lógica ya existente de fotos clínicas (FCLI-10): compresión client-side, bucket privado en Supabase Storage, servido solo por endpoint autenticado.

Se evaluó primero un bucket público separado (más simple: `<img src>` directo, sin fetch autenticado) pero el usuario lo rechazó explícitamente — el logo debe vivir en el **mismo bucket privado** ya usado para fotos clínicas, manteniendo el mismo nivel de seguridad. Esto tiene una consecuencia en cascada: como el bucket es privado, ningún consumidor puede usar `<img src="...">` directo — todos deben traer el logo como Blob autenticado y armar un object URL, igual que `treatment-images.component.ts` ya hace.

## Alcance

### 1. Backend — Storage

Sin bucket nuevo, sin variable de entorno nueva. `backend/app/utils/storage.py` no requiere cambios — ya soporta `upload_object(path, data, content_type)` / `download_object(path)` contra el bucket configurado en `SUPABASE_STORAGE_BUCKET`.

Path estable por clínica dentro de ese mismo bucket: `clinic_{id}/logo.jpg`. Subir un logo nuevo pisa el anterior automáticamente vía `x-upsert: true` (ya usado por `upload_object`) — no hace falta endpoint de borrado. `compressImage()` siempre re-codifica a `.jpg`, así que la extensión del path nunca varía.

**`Clinic.logo_url` se repurpose**: deja de ser una URL externa de texto libre y pasa a almacenar el **path interno dentro del bucket** (ej. `"clinic_3/logo.jpg"`), escrito únicamente por el backend tras una subida exitosa. Ya no es editable como texto — sin migración nueva (la columna ya existe, `String(500)`, alcanza para un path).

### 2. Backend — Endpoints

- **`POST /api/platform/clinics/<id>/logo`** (multipart, `platform_admin_required`, en `platform_admin.py`): valida el archivo igual que `_read_upload_or_error()` (`routes/treatments.py`, reutilizar la misma lógica: `ALLOWED_IMAGE_TYPES`, `MAX_IMAGE_BYTES`), sube al bucket con el path estable, guarda ese path en `clinic.logo_url`, retorna el `clinic.to_dict()` actualizado.
- **`GET /api/clinic/logo`** (self-scoped por `current.clinic_id`, `clinical_access_required`, en `clinic.py`): sirve los bytes del logo de la clínica del usuario autenticado. 404 si no tiene `clinic_id` o no tiene logo.
- **`GET /api/platform/clinics/<id>/logo`** (id-scoped, `platform_admin_required`, en `platform_admin.py`): mismo servido, pero por id explícito — necesario porque un platform admin no tiene "su propia" clínica.

Ambos endpoints de lectura comparten una función interna `_serve_clinic_logo(clinic)` (mismo patrón de streaming que `get_treatment_image_file` en `routes/treatments.py`: `storage.download_object(path)` → `Response(data, mimetype=...)`), para no duplicar la lógica de bajar el archivo del bucket y armar la respuesta.

**Exposición del path en las respuestas JSON** (cada endpoint arma su propio valor, apuntando al endpoint correcto de su app — son dos apps separadas, cada una con su propio endpoint de logo, no un valor universal):
- `GET /api/clinic/info` (usado por `frontend/`, en `clinic.py`): `"logo_url": "/api/clinic/logo"` si `clinic.logo_url` (el path interno) es truthy, si no `None`.
- `Clinic.to_dict()` (usado por `GET /api/platform/clinics/<id>`, consumido por `admin-frontend`): `"logo_url": f"/api/platform/clinics/{self.id}/logo"` si `self.logo_url` es truthy, si no `None`.

### 3. Frontend (`frontend/`) — consumo en la vista imprimible

`treatment-receta.component.ts` (ya existe, de FCLI-11 Task 9-10) agrega: si `clinic()!.logo_url` es truthy, llamar a un nuevo `ClinicService.getLogoBlob(): Observable<Blob>` (`GET /api/clinic/logo`, `responseType: 'blob'`), crear un object URL vía `DomSanitizer.bypassSecurityTrustUrl` (mismo patrón que `treatment-images.component.ts::loadThumbs()`), y bindear `<img [src]="logoObjectUrl()">` en vez de `[src]="clinic()!.logo_url"` directo. Revocar el object URL en `ngOnDestroy` (mismo patrón, `revokeAll()`).

### 4. Frontend (`admin-frontend`) — subida + preview

- Portar `compressImage()` (copia literal, ~70 líneas, sin dependencias externas) a `admin-frontend/src/app/shared/utils/image-compression.ts` — son apps Angular separadas, no comparten código fuente. Parámetros para logo: `maxDim=400, quality=0.85` (más chico que las fotos clínicas de 1600px/0.7 — un logo no necesita tanta resolución — pero con más calidad, ya que suele tener texto/detalle fino que la compresión JPEG agresiva degrada).
- `PlatformService` agrega `uploadClinicLogo(clinicId, blob, filename): Observable<{clinic: Clinic, message: string}>` (`POST /api/platform/clinics/<id>/logo`, multipart) y `getClinicLogoBlob(clinicId): Observable<Blob>` (`GET /api/platform/clinics/<id>/logo`, `responseType: 'blob'`).
- `clinic-detail.component.ts/html`: reemplaza el `<input type="text" name="logo_url">` de FCLI-11 Task 12 por `<input type="file" accept="image/*">`. La subida es **inmediata al seleccionar el archivo** (llamada propia, con su propio estado de carga — no espera al botón "Guardar cambios" del resto del formulario; mismo patrón ya establecido en fotos clínicas). Preview del logo actual (vía blob + object URL, mismo mecanismo que el punto 3) en modo Ver y modo Editar.

## Fuera de alcance

- Botón para quitar el logo por completo (solo reemplazar, sin opción de volver a "sin logo").
- Recorte/editor de imagen en el navegador (solo redimensionar + comprimir, igual que fotos clínicas).
- Migración de datos: cualquier `logo_url` existente cargado como texto libre por la versión anterior de Task 12 queda huérfano (ya no apunta a un path válido dentro del bucket) — dado que el ambiente de testing no tiene datos reales cargados aún, no se contempla migración de esos valores.

## Testing / verificación

Sin suite de tests automatizada — verificar manualmente, en vivo:
1. Desde `admin-frontend`, subir un logo a una clínica → confirmar que aparece el preview inmediatamente.
2. Recargar la página → confirmar que el preview persiste (bytes realmente servidos desde el bucket vía el endpoint autenticado, no solo estado en memoria).
3. Subir un segundo logo a la misma clínica → confirmar que reemplaza al anterior (mismo path, sin objetos huérfanos).
4. Desde `frontend/`, abrir `/treatments/<id>/receta` para un paciente de esa clínica → confirmar que el logo aparece en el encabezado.
5. Confirmar que un usuario clínico no-platform-admin puede `GET /api/clinic/logo` de su propia clínica, y que NO puede `GET /api/platform/clinics/<id>/logo` de ninguna clínica (debe dar 403).
6. Confirmar que subir un archivo no-imagen (o mayor a `MAX_IMAGE_BYTES`) es rechazado con el mismo mensaje de error que ya usan las fotos clínicas.
