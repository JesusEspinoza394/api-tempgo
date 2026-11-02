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
    telemetry.py
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

## Lecturas del Arduino HC-05

El HC-05 transmite líneas JSON como esta:

```json
{"producto":"Refrigerados","temperatura":3.2,"estado":"OPTIMO"}
```

La API recibe las lecturas en `POST /api/lecturas` y las guarda en la tabla
`lecturas_temperatura`. El campo `fecha_creacion` lo asigna el servidor en UTC.
`GET /api/lecturas?limit=100` devuelve las más recientes (máximo 500). La API
verifica que el estado coincida con la temperatura y el perfil:

- `Refrigerados`: 0 a 4 °C
- `FrutasVerduras`: 8 a 12 °C
- `Congelados`: -22 a -16 °C (rango del sketch Arduino)

Después de desplegar este cambio, crea la tabla nueva en Neon una sola vez. En
la Shell de Render ejecuta:

```bash
python -m flask --app run init-db
```

Si no tienes disponible la Shell de Render, ejecuta el mismo comando localmente
con `.env` apuntando a la base Neon. No publiques esa URL ni sus credenciales en
GitHub. `init-db` crea las tablas que falten y no borra los datos existentes.

### Arquitectura Android: Bluetooth → HTTP → API → página

El HC-05 es Bluetooth clásico (SPP), no Web Bluetooth. El flujo previsto es:

```text
Arduino + HC-05
    → Bluetooth clásico
    → Serial Bluetooth Terminal en Android
    → puente/función Android que haga HTTP POST
    → API HTTPS de Render
    → tabla lecturas_temperatura en Neon
    → página web consulta GET /api/lecturas
```

Serial Bluetooth Terminal recibe y muestra el texto del HC-05. Para que las
lecturas lleguen automáticamente a la API, el teléfono también debe tener una
función o aplicación puente que, por cada línea JSON recibida, haga una petición
HTTP POST. Si la configuración de Serial Bluetooth Terminal solo muestra o
guarda el texto, no realiza ese POST por sí sola; en ese caso se necesita una
app/automatización Android compatible con Bluetooth SPP y solicitudes HTTP. No
se puede reemplazar este puente con `fetch()` en la página, porque el navegador
no tiene acceso al Bluetooth clásico SPP del HC-05.

El puente debe ignorar el menú inicial y las líneas de estado que no sean JSON,
y reenviar el JSON sin cambiar los nombres de sus campos. Ejemplo de petición
que debe generar Android para cada lectura:

```http
POST https://TU-API.onrender.com/api/lecturas
Content-Type: application/json

{"producto":"Refrigerados","temperatura":3.2,"estado":"OPTIMO"}
```

La respuesta correcta es `201 Created`. Reemplaza `TU-API` por el nombre real
del servicio en Render. Para probar manualmente el endpoint desde una consola:

```bash
curl -X POST "https://TU-API.onrender.com/api/lecturas" \
  -H "Content-Type: application/json" \
  -d '{"producto":"Refrigerados","temperatura":3.2,"estado":"OPTIMO"}'
```

La página TempGo no recibe Bluetooth directamente: consulta las lecturas ya
guardadas en la API. Por ejemplo, puede solicitar las últimas 100 cada cierto
intervalo:

```javascript
const API_URL = "https://TU-API.onrender.com/api";

async function cargarLecturas() {
  const response = await fetch(`${API_URL}/lecturas?limit=100`);
  if (!response.ok) {
    throw new Error(`Error al consultar lecturas: ${response.status}`);
  }
  return response.json();
}
```

La API tiene CORS habilitado para `/api/*` y usa HTTPS en Render. El endpoint
acepta escrituras sin autenticación; para un uso público conviene protegerlo
antes de exponerlo a Internet.

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
