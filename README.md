# API Flask + Neon PostgreSQL

Estructura inicial para una API REST con Flask y PostgreSQL alojado en Neon.

## Estructura

```text
app/
  api/
    __init__.py
    auth.py
    health.py
    resources.py
  __init__.py
  config.py
  extensions.py
  models.py
.env.example
.gitignore
requirements.txt
run.py
```

## Instalación

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con la cadena de conexión que entrega Neon. La URL debe usar `sslmode=require`.

## Ejecución

```powershell
python run.py
```

La comprobación inicial está disponible en `http://127.0.0.1:5000/api/health`.

Desde una aplicación frontend usa esta URL base completa:

```javascript
const API_URL = "http://127.0.0.1:5000/api";
fetch(`${API_URL}/health`);
```

No uses solamente `/api/...` si el frontend está siendo servido por Five Server, Live Server u otro servidor diferente al puerto `5000`.

## Tablas y endpoints

Los modelos corresponden a las tablas existentes en Neon:

- `alimentos_congelados`: `/api/congelados`
- `alimentos_refrigerados`: `/api/refrigerados`
- `alimentos_verduras`: `/api/verduras`
- `usuarios`: `/api/usuarios`

Cada recurso tiene un endpoint `GET` para listar y un endpoint `POST` para crear registros.

## Autenticación

Registrar un usuario:

```http
POST /api/auth/register
Content-Type: application/json

{
  "nombre": "Ana",
  "email": "ana@example.com",
  "password": "ClaveSegura123",
  "edad": 25
}
```

Iniciar sesión:

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "ana@example.com",
  "password": "ClaveSegura123"
}
```

Ambos endpoints devuelven un `token`. Para verificarlo, envíalo como `Authorization: Bearer <token>` a `GET /api/auth/verify`. El token dura una hora por defecto.

Los usuarios creados antes de agregar `password_hash` deberán registrarse nuevamente o recibir una contraseña mediante un flujo administrativo antes de poder iniciar sesión.

Para crear las tablas desde los modelos en una base nueva:

```powershell
$env:FLASK_APP = "run.py"
python -m flask init-db
```

La aplicación no crea tablas automáticamente al arrancar.

## Recuperación de contraseña

Configura estas variables en el servicio de API de Render y en el archivo `.env`
local. `FRONTEND_URL` debe ser el origen publicado del frontend, sin una barra
final. `SMTP_FROM` debe ser una dirección autorizada por tu proveedor de correo.

- `FRONTEND_URL`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`
- `SMTP_USE_TLS=true` para STARTTLS (puerto 587), o `SMTP_USE_SSL=true` para
  TLS implícito (puerto 465), pero no ambos.
- `PASSWORD_RESET_TOKEN_MAX_AGE=1800` (30 minutos)

La API expone `POST /api/auth/forgot-password` con `{ "email": "..." }` y
`POST /api/auth/reset-password` con `{ "token": "...", "password": "..." }`.
El primer endpoint siempre responde con un mensaje genérico cuando el servicio
de correo está configurado, tanto si la cuenta existe como si no. El enlace es
de un solo uso y vence según `PASSWORD_RESET_TOKEN_MAX_AGE`.
