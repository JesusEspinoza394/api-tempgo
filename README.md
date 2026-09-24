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
