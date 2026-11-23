Curado UV selectivo — software de PC

Instalación
-----------

Ejecutar desde la raíz del proyecto. Se recomienda Python 3.12 para contar
con una versión compatible con ONNX Runtime y el resto de dependencias.

  python3.12 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  mkdir -p models
  curl --fail --location --output models/nail-seg.onnx https://raw.githubusercontent.com/austingg/finger-nail-seg/main/models/nail-seg.onnx

Se usa el modelo YOLOv8 de https://github.com/austingg/finger-nail-seg.
El emulador solo requiere Python y un pseudo-terminal POSIX. El modo demo
usa máscaras sintéticas y coordenadas fijas.

Probar el modelo en una foto cualquiera, sin calibración y sin robot:

  .venv/bin/python -m software.vision.onnx_segmenter foto.jpg --output data/deteccion_onnx.png
  xdg-open data/deteccion_onnx.png

La vista previa indica cuántas uñas detectó y dibuja sus máscaras y centros.
Para recuperar el método anterior, instalar MediaPipe y descargar su modelo:

  .venv/bin/python -m pip install 'mediapipe>=0.10.32,<0.11'
  curl --fail --location --output models/hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

Luego pasar --segmenter contours al controlador.

Página web para analizar una foto
-------------------------------

  .venv/bin/python -m software.vision.web_server

Abrir http://127.0.0.1:8080 en el navegador y elegir o arrastrar una imagen
JPG, PNG o WebP de hasta 15 MB. El resultado muestra las máscaras, sus
centros y el número de uñas detectadas, y puede descargarse como JPG.
El servidor procesa la foto localmente con nail-seg.onnx. La página no
requiere calibración, cámara ni ESP32. Si el puerto está ocupado, pasar
--port 8081 al comando y abrir http://127.0.0.1:8081.

Demo reproducible
-----------------

Terminal 1. El emulador imprime el nombre del pseudo-terminal.

  .venv/bin/python mock_esp32.py --speed 10

Terminal 2. Sustituir /dev/pts/NUM por el puerto impreso.

  .venv/bin/python -m software.orchestrator.cure_controller --config data/demo_config.json --demo --yes --port /dev/pts/NUM --capture data/demo.png --duration-ms 150
  .venv/bin/python -m software.evaluation.metrics data/demo.npz --log data/experiment_logs.csv --output data/evaluation

El PNG muestra máscaras y contornos de los spots. El NPZ guarda las máscaras,
la homografía y el radio. El controlador agrega una fila CSV por comando
intentado. El emulador aplica el contrato a 115200 baud con un objeto JSON UTF-8
por línea. DONE se emite al terminar la duración simulada de CURE. ABORT
cancela el CURE activo. La telemetría del mock es sintética.

Calibración e integración
-------------------------

Copiar data/demo_config.json a un archivo de configuración propio. Retirar
simulation_only después de sustituir sus valores con las medidas reales.
Confirmar L1, L2, origen, área de trabajo, límites articulares, signos de
los ejes y rama del codo con el firmware. Los límites están en grados y
theta2 es relativa al primer eslabón. Medir el radio del spot en milímetros.

En calibration.image_px y calibration.world_mm deben aparecer las cuatro
correspondencias en el mismo orden. Con ArUco se sustituyen ambas listas
por calibration.markers, una lista de cuatro entradas con esta estructura:

  {"id": 0, "corner": 0, "world_mm": [0, 0]}

corner es el índice de la esquina detectada por OpenCV (0–3). La cámara
debe conservar la geometría y resolución de calibración. El controlador
comprueba image_size_px cuando está definida, y usa la primera homografía
ArUco encontrada durante la sesión. roi_px admite [x, y, ancho, alto].
hand_bbox_px admite [izquierda, arriba, derecha, abajo] con el borde
derecho e inferior excluidos.

Validar con puntos adicionales de una cuadrícula. El JSON de validación
contiene image_px y reference_mm como listas de pares. Para ArUco, agregar
--image con la foto de los marcadores.

  .venv/bin/python -m software.calibration.homography_ik config_real.json grid.json

Vista previa en cámara. SPACE confirma los cinco objetivos si son válidos.
ESC sale o envía ABORT durante la secuencia. S guarda la captura solicitada
con --capture. Sin --port, el controlador solo muestra la vista previa.

  .venv/bin/python -m software.orchestrator.cure_controller --config config_real.json --camera 0 --capture data/captura_01.png

Para integración, agregar --port con el puerto del ESP32 y --duration-ms
con la duración acordada. Confirmar los interlocks y validar el movimiento
en el banco con la emisión UV deshabilitada antes de los ensayos.

Para evaluar imágenes archivadas, sustituir --camera por --image,
--preview-only y --capture. Puede ejecutarse en lote con el siguiente
ejemplo para archivos PNG. El primer comando crea el directorio de salida.

  mkdir -p data/capturas
  for img in imagenes/*.png; do
    [ -f "$img" ] || continue
    nombre=$(basename "$img" .png)
    .venv/bin/python -m software.orchestrator.cure_controller --config config_real.json --image "$img" --preview-only --capture "data/capturas/$nombre.png" || break
  done

Evaluación
----------

  .venv/bin/python -m software.evaluation.metrics data/capturas/*.npz --references data/anotaciones --log data/experiment_logs.csv --output data/evaluation

Cada NPZ de referencia debe tener el mismo nombre que la captura. Incluir
ids (1 a 5) y masks (N × H × W, valores binarios). Con ONNX, numerar
de izquierda a derecha en la imagen; con --segmenter contours, del pulgar
al meñique. En ONNX los IDs son posicionales y una detección faltante
puede cambiar los IDs de las detecciones siguientes.
Opcionalmente incluir hand_bbox_px, hand_mask (H × W, silueta binaria)
y measured_spots_mm (N × 2, en el orden de ids). Si no hay anotaciones,
omitir --references. Sin una región de mano definida, puede especificarse
--hand-bbox LEFT TOP RIGHT BOTTOM.

La confianza es la puntuación de detección de YOLO o, con el método
de contornos, la puntuación geométrica del contorno.
IoU y error respecto a la anotación requieren referencias. El error de
apuntado físico requiere los centros medidos. SERR se calcula como
100 × (1 − área de piel bajo la unión de spots / área de piel en la región
base). Con un cuadro delimitador sin silueta se usa un proxy geométrico.
Los centros medidos permiten estimar el área del spot con el radio circular
configurado. El dato skin_spill_est queda en la telemetría del firmware.
Los CSV incluyen medias, desviaciones estándar muestrales y tamaños de
muestra. Las figuras se exportan en PNG a 300 DPI y PDF.

El borrador IEEEtran está en paper/persona_2.tex. Las figuras y resultados
del paper se completan con capturas, anotaciones y mediciones reales.
