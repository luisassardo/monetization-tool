# Monetización · Archivo de Meta en América Latina

Una herramienta de **[J-Lab](https://j-lab.tools)** para explorar y consultar el archivo de monetización de Meta: las cuentas de Facebook e Instagram inscritas en los programas de redistribución de ingresos de Meta en América Latina.

> En producción: **https://monetizacion.j-lab.tools**

Está pensada para periodistas que investigan cómo Meta canaliza dinero a creadores y medios: encontrar redes coordinadas, asimetrías regionales y crecimientos atípicos que no son visibles en las herramientas oficiales.

## 🚀 Características

- **Dashboard** con visualizaciones y estadísticas en vivo
- **Chat con IA real** (Claude, con _tool-use_) que responde **basándose en la base de datos** — sin inventar cifras
- **Análisis para investigación**: ráfagas coordinadas, migración de programas, brecha de verificación, asimetría entre países, crecimiento atípico
- **Tabla interactiva** con filtros, búsqueda y ordenamiento
- **Páginas individuales** por cuenta
- **Widget embebible** para Ghost y otros blogs
- **Bilingüe** ES/EN · tema claro/oscuro
- **API REST** para integraciones

## 🤖 Chat con IA (grounded)

El endpoint `POST /api/ai/chat` usa **Claude con _tool-use_** sobre un conjunto de funciones de consulta seguras (top de cuentas, por país/año/programa/idioma, búsqueda, estadísticas). Claude elige las herramientas y compone una respuesta en el idioma del usuario, citando cifras exactas. No ejecuta código ni SQL arbitrario.

- Requiere `ANTHROPIC_API_KEY` (lado servidor). Configúrala como secreto en Render.
- **Sin clave**, el chat degrada elegantemente al motor local de palabras clave (`engine: "local"`) — la herramienta sigue funcionando.
- Cualquier error/límite también degrada al motor local (`engine: "local-fallback"`, HTTP 200).

Variables de entorno (ver `.env.example`):

| Var | Default | Descripción |
|-----|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Clave Anthropic. Vacía = motor local. |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Modelo del chat (estándar J-Lab). |
| `AI_MAX_TOOL_TURNS` | `6` | Máx. de turnos de herramientas por consulta. |

## 📊 Visualizaciones y análisis

Panorama: cuentas por país (dona), programas (barras), creación por año (línea), top 10.
Análisis para investigación (`/api/analysis/*`): ráfagas coordinadas, migración de programas, brecha verificadas/no verificadas, asimetría entre países, outliers de crecimiento. **Son pistas para investigar, no veredictos.**

## 🔄 Actualizar datos (importador)

No hay API pública del archivo. Los datos frescos vienen del botón **"Export CSV"** en
[monetization.wtf/monetization-archive](https://www.monetization.wtf/monetization-archive).

1. En el archivo, exporta un CSV (puedes filtrar por país o exportar todo).
2. Normaliza y filtra a América Latina con el importador:

```bash
python scripts/import_archive.py --input raw_export.csv --dry-run    # revisa el resumen
python scripts/import_archive.py --input raw_export.csv --output data/accounts.csv
```

El importador es robusto a las inconsistencias del CSV crudo (casing de columnas, UTF-8 inválido, escapes, nombres de idioma no estándar, fechas fantasma/epoch). Filtra a los países de América Latina por **código ISO-2** y deduplica por `account_id`. El esquema de salida son las 17 columnas estándar (ver el _docstring_ del script). Luego haz redeploy.

## 🔧 Desarrollo local

```bash
git clone https://github.com/luisassardo/monetization-tool
cd monetization-tool
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (opcional) export ANTHROPIC_API_KEY=sk-ant-...   # activa el chat con Claude
python app.py
# Abrir http://localhost:5000
```

## 🛠️ Despliegue (Render)

1. Conecta el repo en [render.com](https://render.com) → New → Blueprint (detecta `render.yaml`).
2. Añade `ANTHROPIC_API_KEY` como **secreto** en el dashboard de Render (no lo commitees).
3. Apunta el dominio `monetizacion.j-lab.tools` al servicio.

Manual: Build `pip install -r requirements.txt` · Start `gunicorn app:app --bind 0.0.0.0:$PORT`.

## 📝 Integración con Ghost (widget)

```html
<iframe
  src="https://monetizacion.j-lab.tools/widget"
  width="100%" height="900" frameborder="0"
  style="border:0; overflow:hidden;"></iframe>
```

## 🔗 Endpoints de la API

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` · `/cuenta/<id>` · `/widget` | GET | Páginas (dashboard, detalle, widget). `?lang=es\|en` |
| `/api/stats` | GET | Estadísticas generales |
| `/api/accounts` | GET | Lista de cuentas (paginada, filtrable) |
| `/api/account/<id>` | GET | Datos de una cuenta |
| `/api/filters` | GET | Opciones de filtros |
| `/api/chart/locations` · `/timeline` · `/monetization` | GET | Datos para gráficos |
| `/api/analysis/coordinated-bursts` | GET | Cuentas creadas el mismo día/país (`?min=3`) |
| `/api/analysis/program-migration` | GET | Programas por cohorte de año |
| `/api/analysis/verified-gap` | GET | Verificadas vs no verificadas por país |
| `/api/analysis/country-asymmetry` | GET | Métricas normalizadas por país |
| `/api/analysis/growth-outliers` | GET | Páginas jóvenes con audiencias atípicas |
| `/api/ai/chat` | POST | **Chat con IA** (Claude tool-use; fallback local) |
| `/api/ai/status` | GET | Si la IA está habilitada + modelo |
| `/api/query` | POST | Motor local de palabras clave (legacy) |

### Parámetros de `/api/accounts`
`page`, `per_page` (max 100), `search`, `location`, `verified` (`true`/`false`), `language`, `min_subs`, `sort`, `order` (`asc`/`desc`).

## 📁 Estructura

```
monetization-tool/
├── app.py                     # Backend Flask + tools de IA + análisis
├── requirements.txt
├── render.yaml · Procfile · runtime.txt
├── .env.example
├── scripts/
│   └── import_archive.py      # Normalizador de export → data/accounts.csv
├── static/css/tokens.css      # Sistema de diseño J-Lab (vendored)
├── data/accounts.csv          # Datos (América Latina)
└── templates/
    ├── index.html             # Dashboard
    ├── account.html           # Detalle de cuenta
    └── widget.html            # Widget embebible
```

## 📜 Licencia y atribución

Datos: **[monetization.wtf](https://monetization.wtf)** — mantenido por [WHAT TO FIX](https://www.whattofix.tech/) con apoyo de Luminate · ©️ CC BY-ND 4.0 · [Términos](https://monetization.wtf/terms)

Herramienta: J-Lab, con atribución a Vector Crítico. Código bajo licencia MIT (ver `LICENSE`).
