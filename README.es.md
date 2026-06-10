# edumints SCORM MCP

> **Un servidor MCP que ensambla cursos de e-learning interactivos y compatibles con SCORM.**
> Tú (o un cliente de IA como Claude) eres el **autor**; este servidor es el **ensamblador**.
> Describe un curso como una especificación estructurada — el servidor valida, renderiza y empaqueta
> un **ZIP SCORM autónomo** que funciona en cualquier LMS (Moodle, SCORM Cloud, …).

**🌐 Idiomas:** [English](README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Azərbaycanca](README.az.md) · [Қазақша](README.kk.md) · [Кыргызча](README.ky.md)

Código abierto, desarrollado por la plataforma **[edumints.com](https://edumints.com)**. Pensado para
**auto-alojarse** — ejecútalo en tu propia computadora o servidor — y **abierto a contribuciones**.

---

## La idea (un enfoque diferente)

La mayoría del e-learning se construye a mano con pesadas herramientas de escritorio. Aquí, un **cliente
de IA describe el curso** (objetivos, pantallas, cuestionarios, ramificación, multimedia) mediante el
[Model Context Protocol](https://modelcontextprotocol.io), y el servidor hace lo difícil: validación,
temas premium, renderizado HTML accesible, el puente del runtime SCORM y el empaquetado. El resultado es
un paquete SCORM conforme a los estándares, sin dependencia de proveedor.

**Autor = el cliente MCP · Ensamblador = este servidor.**

## Características

- **26 tipos de pantalla** — título, contenido, opción múltiple, verdadero/falso, completar huecos,
  arrastrar y soltar, hotspot, escenario ramificado, acordeón, pestañas, tarjetas, emparejamiento,
  ordenar, línea de tiempo, lottie, **simulación de software guiada**, vídeo, resumen,
  **escenario de decisión**, **carrera de términos**, **sala de escape**, **diagrama etiquetado**,
  **gráfico de datos**, **comparación de imágenes**, **desglose de resultados**,
  **encuesta / reflexión**.
- **Reproductor de escenario tipo diapositiva** — escenario fijo 16:9 que se adapta a cualquier
  pantalla, una barra de reproducción (play/buscar/subtítulos/menú/repetir) y **revelado por línea de
  tiempo** sincronizado con la narración. Menú de índice agrupado por secciones. Tamaño de escenario
  ajustable; totalmente responsivo/móvil; iconos SVG en línea (sin emojis).
- **Lógica y gamificación** — variables/estado, visibilidad condicional, ramificación, HUD de puntos y
  temporizador.
- **Evaluación** — preguntas alineadas con retroalimentación en aciertos/errores, puntuación escrita en SCORM.
- **Multimedia** — ingesta entre-MCP (trae audio/imagen/vídeo desde tus propios MCP → `add_asset`),
  procesamiento con ffmpeg, **vídeo programático de motion-graphics/visualización de datos** (HyperFrames)
  y un **TTS turco** integrado (Piper, sin conexión) para narración rápida.
- **Temas y accesibilidad** — presets claros/neutros/alto contraste, tokens de marca, orientado a WCAG,
  respeta `prefers-reduced-motion`.
- **SCORM 1.2 y 2004**, empaquetado determinista, límites de coste, funciones pesadas opt-in/perezosas
  (nada se carga salvo que un curso lo use).

## Inicio rápido (auto-alojamiento)

### Docker (recomendado)
```bash
git clone https://github.com/kemalyy/edumints-scorm-mcp.git
cd edumints-scorm-mcp
docker build -t edumints-scorm-mcp .
docker run -p 8000:8000 -v "$PWD/data:/data" edumints-scorm-mcp
# Endpoint MCP: http://localhost:8000/mcp   ·   salud: http://localhost:8000/health
```
La imagen incluye todo lo necesario para las funciones opcionales (ffmpeg, Node + HyperFrames para
vídeo, Piper + una voz turca para TTS).

### Local (Python)
```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[tts]"          # ".[tts]" añade el TTS turco sin conexión (Piper); omítelo para saltarlo
python server.py              # sirve el MCP por HTTP
```
Para la generación de vídeo, instala también Node 22+ y HyperFrames (`npm i -g hyperframes`) + ffmpeg.

### Configuración
Copia `.env.example` y ajústalo (directorio de datos, cuotas, URL base, TTL). Todas las opciones están
en el archivo. No se requieren secretos para ejecutarlo localmente.

## Conectar un cliente de IA

Apunta cualquier cliente MCP a `http://<tu-host>:8000/mcp`:
- **Claude** (escritorio/web/Code) — añádelo como conector / servidor MCP.
- **Antigravity** y otros clientes MCP — el mismo endpoint (HTTP/Streamable).

Luego pide: *"Crea un curso interactivo de 6 minutos sobre X con un cuestionario y un resumen."* El
cliente llama a las herramientas de abajo; obtienes un ZIP SCORM descargable.

> Se combina con la **skill de autoría** (una Claude Agent Skill que enseña a un cliente de IA a crear
> cursos de alta calidad con este servidor): https://github.com/kemalyy/edumints-scorm-skill

## Herramientas clave (MCP)

| Herramienta | Propósito |
|---|---|
| `build_from_spec` | Una especificación JSON → proyecto validado + ZIP SCORM empaquetado (la vía principal) |
| `create_project` / `add_screen` / `update_screen` / … | Edición granular e incremental |
| `set_theme` / `set_tracking` | Temas + reglas de finalización/puntuación |
| `add_asset` | Ingesta de audio/imagen/vídeo (data-URI o https, protegido contra SSRF) |
| `synthesize_speech` | Narración turca integrada (Piper, sin conexión) → recurso de audio |
| `make_video_from_image_audio` / `render_motion_video` / `render_screen_video` | Vídeo (ffmpeg / HyperFrames) |
| `preview` / `validate_package` / `build_package` | Previsualizar, validar, descargar el ZIP SCORM |

## Arquitectura

```
Cliente MCP (autor)  ──►  scorm-mcp (ensamblador)
                            ├─ core/        modelos (Pydantic), empaquetado, almacenamiento
                            ├─ components/  renderizador HTML + motor de runtime + compilador de vídeo
                            ├─ auth/        API-key + OAuth, protecciones SSRF
                            ├─ themes/      tokens de diseño / presets
                            ├─ runtime/     runtime SCORM incorporado (scorm-again, MIT)
                            └─ server.py    herramientas FastMCP (HTTP)
```
Salida: un `index.html` autónomo + `imsmanifest.xml` + recursos + runtime SCORM, comprimido.

## Contribuir

Issues y PRs son bienvenidos. El código favorece módulos pequeños y enfocados, cambios aditivos y
compatibilidad hacia atrás. Consulta [CONTRIBUTING.md](CONTRIBUTING.md).

## Pruebas

Ejecuta las pruebas con `pytest`.

## Licencias

- Este proyecto: **MIT** — ver [LICENSE](LICENSE).
- Componentes de terceros incluidos (scorm-again, lottie-web): ver [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Desarrollado por **edumints.com**. SCORM es una marca de ADL; otros nombres de productos mencionados son
marcas de sus respectivos propietarios (uso nominativo únicamente).


<!-- synced: 5bd4f67 -->
