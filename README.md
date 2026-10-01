Read this in English (#english) | Leer en Español (#espanol)

---

Version en Español

WSOS Scripting 1.0
Autor: Wolfram Steel

¡Hola! Qué gusto tenerte por aquí. Si alguna vez te has visto en la tediosa tarea de rebuscar información técnica por la web, recopilar enlaces a mano y preparar datasets limpios para tus proyectos o bases de conocimiento, sabrás perfectamente lo frustrante y lento que llega a ser.

WSOS Scripting 1.0 nace precisamente para quitarte ese dolor de cabeza. Es una herramienta de escritorio ligera, rápida y muy cómoda para automatizar todo ese flujo de trabajo sin perder el control en ningún momento.

¿Qué puedes hacer con esta herramienta?

* Interfaz Gráfica Moderna (Flet): Olvídate de estar atado a la consola si no te apetece. Disfrutas de un panel visual en modo oscuro muy cuidado, con una consola en tiempo real que te muestra el paso a paso y un botón directo para abrir la carpeta de resultados. Además, puedes detener cualquier proceso de forma segura en plena ejecución.
* Búsqueda Multirregión Inteligente: Se conecta a DuckDuckGo adaptándose a la región que elijas (España, Estados Unidos, UK o Global). Todo ello acompañado de un filtro estricto que barre la publicidad, rastreadores y parámetros molestos como utm, gclid o fbclid.

Guía de uso paso a paso

1. Crear una categoría previa: Se recomienda encarecidamente que, antes de realizar tu primera búsqueda web, hagas clic en el botón morado de Categorías (arriba a la derecha en la interfaz) y crees una categoría (por ejemplo, llamada prueba). Esto es necesario para poder asociar y guardar las webs encontradas en el archivo JSON.
2. Configurar la Búsqueda Web:
* En el desplegable superior, selecciona la opción Búsqueda webs.
* Escribe tus palabras clave separadas por comas (por ejemplo: python, flet).
* Asigna un nombre al archivo txt de salida (este archivo servirá como copia de respaldo externa al JSON con los enlaces encontrados).
* Selecciona la región geográfica donde quieres realizar la búsqueda.
* Elige la categoría de destino obligatoria que creaste antes (en este caso, prueba).
* En las casillas inferiores, elige uno de los dos modos avanzados disponibles:
* Modo WSOS: Amplía automáticamente tus palabras clave añadiendo modificadores técnicos (github, documentation, tutorial, etc.) para forzar la obtención de código y guías de alto valor, validando el contenido al vuelo y generando un dataset limpio (dataset_wsos_archivo.txt).
* Búsqueda Sucia: Ideal para cuando necesitas un aluvión masivo de enlaces y referencias sin filtros estrictos.




3. Ejecutar y Procesar: Pulsa el botón rojo de Ejecutar Proceso y observa la consola. Una vez finalizado, las webs se habrán guardado en tu categoría prueba.
4. Extraer el contenido: Para completar el ciclo de información, selecciona ahora tu categoría (prueba) en el desplegable principal de la interfaz y dale a ejecutar. El sistema recorrerá las webs guardadas y generará archivos txt con todo su contenido estructurado por lotes.

Puesta en marcha en 1 clic

Para ahorrarte dolores de instalación, cuentas con un script auto-configurador. Solo sigue estos pasos:

1. Clona o descarga este repositorio en tu ordenador.
2. Abre tu terminal en la carpeta del proyecto y ejecuta:
python3 actualizador.py
Este script comprobará las dependencias necesarias (flet, requests, beautifulsoup4, ddgs) y creará una plantilla base de webs.json si no la encuentra.

¿Cómo arrancar la aplicación?

Una vez completado el paso anterior, lanza la interfaz gráfica ejecutando:
python3 main.py

Estructura del proyecto

* actualizador.py: Auto-configurador del entorno y dependencias.
* main.py: Punto de entrada ligero que inicializa la ventana de Flet.
* ui.py: Interfaz gráfica, gestión de hilos y consola de logs en tiempo real.
* scraping.py: Orquestador principal de la lógica de negocio y tareas.
* buscadores.py: Pasarela de comunicación con DuckDuckGo.
* bloqueos.py: Filtros avanzados de saneamiento y bloqueo de rastreadores.
* procesador.py: Procesador HTML inteligente que aísla el ruido y cuida el formato de código.
* categorias.py: Lógica para procesar las categorías por lotes.

¡AVISO LEGAL!
El autor no se hace responsable del mal uso de esta herramienta. Este software ha sido diseñado estrictamente con fines educativos, de investigación y para la automatización de flujos de desarrollo personales. Es responsabilidad de quien lo utiliza cumplir con los términos de servicio de los sitios web consultados y las leyes aplicables.

¡Espero que te sea de gran utilidad en tu día a día! Si te mola, no dudes en adaptarlo a tus necesidades.





--------------------------------------------------------------------------------------------------------------------------






English Version

WSOS Scripting 1.0
Author: Wolfram Steel

Hello! If you have ever found yourself in the tedious task of searching the web for technical information, manually gathering links, and preparing clean datasets for your projects or knowledge bases, you know perfectly well how frustrating and slow it can be.

WSOS Scripting 1.0 was built precisely to take away that headache. It is a lightweight, fast, and very comfortable desktop tool designed to automate that entire workflow without ever losing control.

What can you do with this tool?

* Modern Graphical Interface (Flet): Forget about being tied to a plain console. Enjoy a carefully crafted dark-mode visual panel featuring a real-time log console and a direct button to open the results folder in your local file explorer. Plus, you can safely stop any running process mid-execution thanks to thread control.
* Smart Multi-Region Search: Connects directly to DuckDuckGo, adapting to your chosen region (Spain, USA, UK, or Global), backed by a strict filter that clears out ads, trackers, and annoying parameters like utm, gclid, or fbclid.

Step-by-Step Usage Guide

1. Create a Category First: It is highly recommended to click the purple Categories button at the top right of the interface and create a category (e.g., named test) before running your first web search. This is required to store the discovered websites into the JSON configuration file.
2. Configure Web Search:
* Select Búsqueda webs from the top dropdown menu.
* Type your keywords separated by commas (e.g., python, flet).
* Name your output txt file (this serves as an external backup copy alongside the JSON file).
* Choose your target search region.
* Select the mandatory destination category created earlier (e.g., test).
* Choose between the two advanced modes:
* WSOS Mode: Automatically expands your keywords with technical modifiers (github, documentation, tutorial, etc.) to harvest high-value code and guides, validating content on the fly and generating a clean dataset (dataset_wsos_archivo.txt).
* Dirty Search: Ideal when you need a massive flood of links and references without strict filters.




3. Run and Process: Click the red Execute Process button and watch the console. Once finished, the URLs will be saved under your category.
4. Extract Content: To complete the information cycle, select your category from the main dropdown menu and hit run again. The system will crawl the saved websites and generate txt files containing all extracted content structured in batches.

1-Click Setup

To save you installation headaches, an auto-configurator script is included. Just follow these steps:

1. Clone or download this repository to your computer.
2. Open your terminal in the project folder and run:
python3 actualizador.py
This script will check for required dependencies (flet, requests, beautifulsoup4, ddgs) and create a default webs.json template if missing.

How to Launch the Application?

Once the setup is complete, launch the graphical interface by running:
python3 main.py

Project Structure

* actualizador.py: Environment and dependency auto-configurator.
* main.py: Lightweight entry point initializing the Flet window.
* ui.py: Graphical user interface, thread management, and real-time logs.
* scraping.py: Main orchestrator for business logic and tasks.
* buscadores.py: Robust communication gateway with DuckDuckGo.
* bloqueos.py: Advanced sanitization and tracker-blocking filters.
* procesador.py: Smart HTML processor isolating noise while protecting code formatting.
* categorias.py: Logic for batch-processing categories.

DISCLAIMER!
The author is not responsible for any misuse of this tool. This software has been designed strictly for educational purposes, research, and personal development workflow automation. It is the user's sole responsibility to comply with the terms of service of consulted websites and applicable laws.

I hope this proves useful in your daily workflow! Feel free to adapt it to your needs.
