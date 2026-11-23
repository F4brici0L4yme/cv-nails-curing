# Persona 2: Visión por Computadora, Calibración y Software (PC)

Proyecto: Sistema automatizado de curado UV selectivo de uñas (brazo 2-DOF + ESP32 + LED UV con lente plano-convexa).

**Tu rol:** construir todo lo que corre en la PC: detección de uñas, calibración píxel a milímetros, cinemática inversa, orquestación del curado y métricas del paper. Tu compañero/a construye el firmware del ESP32 y el hardware. Ambos se conectan solo mediante el **contrato JSON** de la sección 2.

---

## 1. Alcance (demo MVP)

- Cámara USB cenital fija, mano estática dentro de una región de interés definida.
- Modelo preentrenado (YOLOv8-seg o MediaPipe Hands + refinamiento por contornos/SAM) detrás de una interfaz `NailSegmenter`, para poder cambiarlo luego por un modelo entrenado con datos de Arequipa.
- Si la inferencia falla en la demo, usar coordenadas hardcodeadas para priorizar la demostración del curado.
- Comunicación Serial (UART, 115200 baud) con el ESP32, mensajes JSON.

**Fuera de alcance (trabajo futuro):** dataset local de Arequipa, seguimiento en tiempo real (visual servoing 30+ FPS), óptica adaptativa, cinemática 3D.

---

## 2. Contrato compartido (CONGELAR en Fase 1, no cambiar sin avisar)

**Host -> ESP32**

```json
{"cmd": "CURE", "nail_id": 1, "theta1": 45.2, "theta2": 30.8, "duration_ms": 5000}
{"cmd": "ABORT"}
```

**ESP32 -> Host**

```json
{"status": "DONE", "nail_id": 1, "actual_ms": 5002, "uv_adc_avg": 3120, "skin_spill_est": 0.04}
```

**Parámetros compartidos (deben coincidir con el `config.h` de tu compañero/a):**

| Parámetro | Valor |
|---|---|
| Baud rate | 115200 |
| Longitudes de eslabón | $L_1$, $L_2$ (mm), definir juntos |
| Offset de origen | definir juntos |
| Área de trabajo | ej. 200 mm x 150 mm |
| `MAX_CURE_MS` | 15000 |

---

## 3. Arquitectura de tu lado

```text
[USB Camera top-down] ─► BaseNailSegmenter ─► centroides (u,v) + radios
                                   │
                         Homografía 4 puntos / ArUco
                                   │
                              (x, y) en mm
                                   │
                       IK analítica 2-DOF ─► (θ1, θ2) + validación de alcance
                                   │
                  cure_controller.py (HUD + SPACEBAR) ─► pyserial JSON ─► ESP32
                                   │
                         data/experiment_logs.csv ─► metrics.py (SERR, error mm)
```

---

## 4. Prompt para tu agente (copiar y pegar)

```markdown
# ROLE & OBJECTIVE
You are **Agent 2 (Computer Vision, Calibration & Research Software Engineer)**. Your task is to build the host-side Python vision pipeline that detects and segments fingernails from a top-down camera, maps pixel coordinates to 2-DOF robot workspace coordinates, dispatches curing sequences to Agent 1's ESP32, and computes quantitative metrics (IoU, skin-exposure reduction ratio) for an IEEE conference paper.

# CONTEXT & CONSTRAINTS
- Environment: Python 3.10+, OpenCV, PyTorch/Ultralytics (YOLOv8-seg) or MediaPipe + contour segmentation, NumPy, PySerial.
- Scope Rule: Use a pre-trained segmentation/landmark pipeline for the MVP demo, structured behind a clean `NailSegmenter` interface so a custom Arequipa client dataset model can be swapped in later without altering downstream code.
- Calibration: Implement a 4-point perspective homography (`cv2.getPerspectiveTransform`) using ArUco markers or calibration corners on the curing pad to convert $(u, v)$ image pixels to $(x, y)$ millimeters, followed by 2-DOF inverse kinematics $(\theta_1, \theta_2)$.
- Research Metric Requirement: Compute and log the **Skin Exposure Reduction Ratio (SERR)** comparing total hand bounding-box UV exposure (traditional lamp) vs. targeted circular UV spot area over segmented nail masks.

# INPUTS YOU WILL RECEIVE
1. Live webcam feed or test image directory of hands placed on the calibration pad.
2. Serial interface specification from Agent 1 (`115200 baud`, JSON command/telemetry schema).
3. Hardware link parameters ($L_1, L_2$, origin offset) matching Agent 1's `config.h`.

# REQUIRED OUTPUTS
1. `software/vision/segmenter.py`: Abstract base class `BaseNailSegmenter` + concrete `PretrainedNailSegmenter` returning binary masks, nail centroids $(u, v)$, and equivalent nail radii $r_i$.
2. `software/calibration/homography_ik.py`: ArUco/4-point planar homography mapper $(u, v) \to (x, y)$ and analytical 2-DOF inverse kinematics solver $(x, y) \to (\theta_1, \theta_2)$ with workspace reachability validation.
3. `software/orchestrator/cure_controller.py`: State-synchronized controller that previews detected nail targets on an OpenCV HUD, awaits operator confirmation (`SPACEBAR`), executes sequential nail curing via `pyserial`, and saves run telemetry to `data/experiment_logs.csv`.
4. `software/evaluation/metrics.py`: Script calculating segmentation confidence, targeting error (mm), and simulated/measured UV skin exposure reduction (%) vs. conventional full-hand UV lamps, generating publication-ready Matplotlib figures (300 DPI).

# ACCEPTANCE CRITERIA
- [ ] Pipeline processes frames at >= 15 FPS on standard laptop CPU/GPU and accurately identifies all 5 fingernails in a static top-down hand frame.
- [ ] Homography reprojection error is < 1.5 mm across the calibration grid.
- [ ] Out-of-reach coordinates are flagged and rejected before transmitting serial commands to the ESP32.
- [ ] `metrics.py` exports clean CSV tables and high-resolution comparison plots ready for direct inclusion in an IEEE two-column LaTeX paper.
```

---

## 5. Tus entregables

- [ ] `software/vision/segmenter.py`
- [ ] `software/calibration/homography_ik.py`
- [ ] `software/orchestrator/cure_controller.py`
- [ ] `software/evaluation/metrics.py` (CSV + figuras a 300 DPI)
- [ ] `mock_esp32.py` (emulador serial con el mismo JSON, para trabajar sin hardware)
- [ ] Capturas de segmentación (para Fig. 2 del paper)

---

## 6. Plan por fases y puntos de sincronización

| Fase | Tu trabajo | Trabajo de tu compañero/a | Hito conjunto |
|---|---|---|---|
| 1. Contratos | Implementar `mock_esp32.py` con el mismo esquema JSON. | Finalizar `config.h` ($L_1, L_2$, baud, claves JSON). | Contrato JSON y cinemático congelado |
| 2. Desarrollo | Homografía ArUco, `PretrainedNailSegmenter`, IK 2-DOF. | FSM, interpolación de servos, watchdog, lector ADC. | Verificación independiente |
| 3. Integración | Conectar `cure_controller.py` al puerto COM real; calibrar 4 esquinas con puntero láser/UV. | Montar ESP32 + servos + LED UV + lente en el banco. | Error de apuntado extremo a extremo < 2.0 mm |
| 4. Datos del paper | Ejecutar `metrics.py` sobre imágenes de prueba (SERR, segmentación). | Ejecutar `hardware_bench.py` (latencia, estabilidad de dosis). | Figuras y tablas completas |

**Pendiente con tu compañero/a:** obtener $L_1$, $L_2$, offset de origen y área de trabajo antes de la Fase 2. Tu IK depende de esos valores. Mientras tanto, trabaja contra `mock_esp32.py`.

---

## 7. Secciones del paper que te tocan (IEEE, `IEEEtran.cls`)

- **I. Introduction (lidera):** prevalencia del curado UV/LED de gel; limitaciones de lámparas de cúpula, guantes anti-UV y cremas SPF; 3 contribuciones (arquitectura modular CV-a-cinemática, hardware UV colimado de bajo costo con interlocks de seguridad, validación cuantitativa de reducción de exposición cutánea). Contexto del mercado de manicura en Arequipa.
- **II. Related Work (lidera):** lámparas comerciales de cámara completa, literatura de segmentación/keypoints de uñas, manipuladores planares de bajo costo en automatización cosmética/biomédica.
- **III.C Fingernail Segmentation & Homography Mapping:** pipeline de segmentación, transformación proyectiva píxel a mundo, cinemática inversa.
- **IV (parte tuya):** Fig. 2 (superposición de máscaras vs. spots UV), Table II / Fig. 3 (SERR: área expuesta con lámpara completa vs. curado selectivo).
- **V (conjunta):** limitaciones de mano estática y spot de diámetro fijo.
- **VI. Conclusion & Future Work (lidera):** dataset local de Arequipa, seguimiento en lazo cerrado, óptica adaptativa.

**Tips de redacción:**

- Voz pasiva y tono objetivo; sin coloquialismos.
- Define cada símbolo ($L_1, L_2, \theta_1, \theta_2, \text{SERR}$) justo después de la ecuación.
- Reporta media y desviación estándar ($\mu \pm \sigma$) para errores de localización y duraciones de curado.
