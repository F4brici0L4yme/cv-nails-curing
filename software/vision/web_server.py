"""Serve the nail detection page and inference API on this computer."""

import argparse
import base64
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.util import find_spec
import json
from pathlib import Path

WEB = Path(__file__).with_name("web")
MAX_UPLOAD = 15 * 1024 * 1024


class DetectorUnavailable(RuntimeError):
    pass


class Detector:
    def __init__(self, model_path):
        self.model_path = model_path
        self.segmenter = None

    def detect(self, image_bytes):
        missing = [name for name in ("cv2", "numpy", "onnxruntime") if find_spec(name) is None]
        problems = []
        if missing:
            problems.append("Faltan las librerías " + ", ".join(missing) +
                            ". Ejecuta .venv/bin/python -m pip install -r requirements.txt.")
        if not self.model_path.is_file():
            problems.append(f"Falta el modelo {self.model_path.name}. Descárgalo en models/ "
                            "siguiendo los comandos de README.txt.")
        if problems:
            raise DetectorUnavailable(" ".join(problems))

        import cv2
        import numpy as np
        from software.vision.onnx_segmenter import OnnxNailSegmenter, annotate

        frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("No se pudo leer la imagen. Prueba con JPG, PNG o WebP.")
        if self.segmenter is None:
            self.segmenter = OnnxNailSegmenter(self.model_path)
        nails = self.segmenter.segment(frame)
        ok, encoded = cv2.imencode(".jpg", annotate(frame, nails), [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise RuntimeError("No se pudo codificar la imagen de salida")
        return {
            "count": len(nails),
            "image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
        }


class Handler(BaseHTTPRequestHandler):
    def send_payload(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def respond(self, status, **payload):
        self.send_payload(status, json.dumps(payload).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/":
            self.send_payload(HTTPStatus.OK, (WEB / "index.html").read_bytes(),
                              "text/html; charset=utf-8")
        else:
            self.respond(HTTPStatus.NOT_FOUND, error="Ruta no encontrada.")

    def do_POST(self):
        if self.path != "/detect":
            self.respond(HTTPStatus.NOT_FOUND, error="Ruta no encontrada.")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_UPLOAD:
            self.close_connection = True
            self.respond(HTTPStatus.BAD_REQUEST, error="Selecciona una imagen de hasta 15 MB.")
            return
        image_bytes = self.rfile.read(length)
        if len(image_bytes) != length:
            self.respond(HTTPStatus.BAD_REQUEST, error="La imagen se recibió incompleta.")
            return
        try:
            result = self.server.detector.detect(image_bytes)
        except DetectorUnavailable as exc:
            self.respond(HTTPStatus.SERVICE_UNAVAILABLE, error=str(exc))
        except ImportError as exc:
            self.log_error("Import failed: %s", exc)
            self.respond(HTTPStatus.SERVICE_UNAVAILABLE,
                         error="Una librería no se pudo cargar. Revisa el error en la terminal.")
        except ValueError as exc:
            self.respond(HTTPStatus.UNPROCESSABLE_ENTITY, error=str(exc))
        except Exception as exc:
            self.log_error("Detection failed: %s", exc)
            self.respond(HTTPStatus.INTERNAL_SERVER_ERROR,
                         error="El modelo no pudo procesar esta imagen. Revisa la terminal.")
        else:
            self.respond(HTTPStatus.OK, **result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", type=Path, default=Path("models/nail-seg.onnx"))
    args = parser.parse_args()
    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.detector = Detector(args.model)
        print(f"Abre http://127.0.0.1:{server.server_port} en tu navegador.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
