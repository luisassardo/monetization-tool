# Cuentas Monetizadas en Facebook - Herramienta de Visualización

Una herramienta interactiva para explorar y consultar datos de cuentas de Facebook que participan en programas de monetización en Centroamérica.

## 🚀 Características

- **Dashboard completo** con visualizaciones de datos
- **Consultas en lenguaje natural** usando IA
- **Tabla interactiva** con filtros y ordenamiento
- **Páginas individuales** para cada cuenta
- **Widget embebible** para Ghost y otros blogs
- **API REST** para integraciones

## 📊 Visualizaciones

- Cuentas por ubicación (gráfico circular)
- Programas de monetización (barras)
- Timeline de creación de cuentas (línea)
- Top 10 cuentas por suscriptores

## 🛠️ Despliegue

### Opción 1: Render (Recomendado - Gratis)

1. Crea una cuenta en [render.com](https://render.com)
2. Conecta tu repositorio de GitHub
3. Haz clic en "New" → "Blueprint"
4. Selecciona tu repositorio
5. Render detectará automáticamente el `render.yaml` y desplegará

**O manualmente:**
1. New → Web Service
2. Conecta tu repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`

### Opción 2: Railway

1. Ve a [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Selecciona tu repositorio
4. Railway detectará automáticamente Flask

### Opción 3: Heroku

```bash
heroku create tu-app-name
git push heroku main
```

### Opción 4: GitHub Pages (Solo frontend estático)

Para una versión estática con datos embebidos, usa el archivo `standalone.html` (ver más abajo).

## 📁 Estructura del Proyecto

```
monetization-tool/
├── app.py              # Backend Flask
├── requirements.txt    # Dependencias Python
├── render.yaml        # Config para Render
├── Procfile           # Config para Heroku
├── data/
│   └── accounts.csv   # Datos de cuentas
└── templates/
    ├── index.html     # Dashboard principal
    ├── account.html   # Detalle de cuenta
    └── widget.html    # Widget embebible
```

## 🔗 Endpoints de la API

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Dashboard principal |
| `/cuenta/<id>` | GET | Detalle de cuenta |
| `/widget` | GET | Widget embebible |
| `/api/stats` | GET | Estadísticas generales |
| `/api/accounts` | GET | Lista de cuentas (paginada) |
| `/api/account/<id>` | GET | Datos de una cuenta |
| `/api/chart/locations` | GET | Datos para gráfico de ubicaciones |
| `/api/chart/timeline` | GET | Datos para gráfico temporal |
| `/api/chart/monetization` | GET | Datos de programas |
| `/api/query` | POST | Consulta en lenguaje natural |
| `/api/filters` | GET | Opciones de filtros |

### Parámetros de `/api/accounts`

- `page`: Número de página (default: 1)
- `per_page`: Resultados por página (default: 25, max: 100)
- `search`: Búsqueda por nombre/handle
- `location`: Filtrar por ubicación
- `verified`: `true` o `false`
- `language`: Filtrar por idioma
- `min_subs`: Mínimo de suscriptores
- `sort`: Campo para ordenar
- `order`: `asc` o `desc`

## 📝 Integración con Ghost

### Método 1: Iframe (Recomendado)

Después de desplegar, usa este código en un bloque HTML de Ghost:

```html
<iframe 
  src="https://TU-APP.onrender.com/widget" 
  width="100%" 
  height="800px" 
  frameborder="0"
  style="border-radius: 12px; overflow: hidden;">
</iframe>
```

### Método 2: Enlace con botón

```html
<div style="text-align: center; padding: 2rem;">
  <a href="https://TU-APP.onrender.com" 
     target="_blank"
     style="display: inline-block; padding: 1rem 2rem; background: #e94560; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">
    Ver herramienta de datos →
  </a>
</div>
```

## 🔄 Actualizar Datos

Para actualizar los datos, simplemente reemplaza el archivo `data/accounts.csv` con el nuevo CSV y haz redeploy.

El CSV debe tener estas columnas:
- `account_id`
- `account_name`
- `account_handle`
- `account_verified`
- `page_created_date`
- `account_subscriber_count`
- `account_language_code`
- `account_language`
- `admin_location_code`
- `admin_location`
- `last_onboarding`
- `first_recorded_monetization`
- `last_recorded_monetization`
- `facebook_instant_articles_session_count`
- `facebook_in_stream_ads_session_count`
- `facebook_ads_on_reels_session_count`
- `facebook_content_monetization_session_count`

## 📜 Licencia

Datos: [Monetization.wtf](https://monetization.wtf) - WHAT TO FIX con apoyo de Luminate  
©️ CC BY-ND 4.0

## 🔧 Desarrollo Local

```bash
# Clonar repositorio
git clone tu-repo
cd monetization-tool

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py

# Abrir http://localhost:5000
```
