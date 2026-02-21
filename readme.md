# 🦁 Lion YT Downloader v1.0.0

**Lion YT Downloader** es una aplicación de escritorio de alto rendimiento diseñada para optimizar radicalmente el flujo de trabajo de descarga de contenido multimedia.

Desarrollada con **Python 3.13** y **PyQt6**, ofrece una interfaz oscura minimalista y robusta, enfocada en:

* ⚡ Velocidad
* 🌍 Compatibilidad universal
* 🗂 Organización avanzada de archivos

---

## ✨ Características Principales

### 🚀 Integración Inteligente (Drag & Drop)

Arrastra enlaces o miniaturas directamente desde tu navegador a la aplicación.

### 🔄 Conversión Automática a MP4 / MP3

Olvídate de formatos incompatibles.
Todo se procesa mediante **FFmpeg**, garantizando compatibilidad total en cualquier dispositivo.

### 🎭 Control de Calidad Selectivo

* **Ultra** → 4K / 8K (Mejor calidad disponible)
* **HD** → Forzado a 1080p o 720p (optimización de espacio)
* **Audio** → MP3 de alta fidelidad (192 kbps)

### 🧠 Detección Inteligente de Duplicados

La aplicación escanea la carpeta de destino y evita descargar archivos ya existentes.

* 🟡 Se marcan en **naranja** para indicar que fueron omitidos.

### 🎨 Semáforo de Estado Visual

| Estado     | Significado                |
| ---------- | -------------------------- |
| 🟢 Verde   | Descargado con éxito       |
| 🟡 Naranja | Ya existía (omitido)       |
| 🔴 Rojo    | Enlace roto o error de red |

---

## 💡 Innovación: Asignación Dinámica de Nombres

Permite organizar tu librería **antes** de iniciar la descarga.

El programa analiza el texto pegado y:

* Si detecta texto justo encima de un enlace → lo usa como nombre del archivo.
* Si no hay texto → usa el título original del video.

### Ejemplo de uso

Puedes pegar directamente en la aplicación:

```text
Entrevista con el CEO
https://www.youtube.com/watch?v=ejemplo1

Documental de Naturaleza 2026
www.youtube.com/watch?v=ejemplo2

https://youtu.be/ejemplo3
```

### Resultado generado:

```
Entrevista con el CEO.mp4
Documental de Naturaleza 2026.mp4
Titulo_Original_De_Youtube.mp4
```

*(El tercero usa el título original al no detectar texto personalizado.)*

### Sistema Robusto

* Corrige automáticamente enlaces que empiezan por `www.`
* Limpia caracteres inválidos (`/ \ : * ? " < > |`)
* Garantiza nombres compatibles con el sistema operativo

---

## 🛠 Instalación y Configuración

### Para Desarrolladores (Código Fuente)

Instala las dependencias:

```bash
pip install PyQt6 yt-dlp pyqtdarktheme
```

---

## ⚙ Requisito Esencial: FFmpeg

Para fusionar audio/video en HD y convertir a MP4 necesitas **FFmpeg**.

### Pasos:

1. Descarga `ffmpeg.exe` y `ffprobe.exe` desde:
   [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)

2. Coloca ambos archivos:

   * En la raíz del proyecto (junto a `main.py`), **o**
   * En la carpeta del ejecutable final

---

## 📦 Generación del Ejecutable (.exe)

Incluye un script automático para Windows.

### Pasos:

1. Asegúrate de tener en la raíz:

   * `icon.ico`
   * `ffmpeg.exe`
   * `ffprobe.exe`

2. Ejecuta:

```bash
build_app.bat
```

3. Introduce el número de versión cuando se solicite.

### Resultado

Se generará un archivo `.zip` listo para distribución que contiene:

* La aplicación (modo carpeta → máxima estabilidad)
* Los binarios de FFmpeg incluidos

---

## 🤝 Software a Medida y Servicios Freelance

Esta herramienta demuestra cómo la automatización puede acelerar procesos creativos y técnicos.

Si necesitas una herramienta personalizada, puedo ayudarte con:

* 🖥 Aplicaciones de Escritorio (Windows, Mac, Linux)
* 🔁 Automatización de Flujos de Trabajo
* 🌐 Web Scraping
* 📊 Procesamiento de Datos
* 🏢 Software de gestión interna

---

## 📩 Contacto

**Email:** [ewejose@gmail.com](mailto:ewejose@gmail.com)

Si quieres optimizar tu trabajo con software diseñado específicamente para tus necesidades, ¡hablemos!

---

## 📄 Licencia

Este proyecto es **código abierto bajo la Licencia MIT**.
Eres libre de usarlo, modificarlo y distribuirlo.

---

Creado con ❤️ por **Ewe**
