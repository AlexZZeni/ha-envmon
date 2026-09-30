"""API HTTP dos sensores de temperatura e umidade."""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
from typing import Any

from flask import Flask, jsonify
from waitress import serve

from sensors import DhtBackend, FakeBackend, SensorReader, parse_sensors

__version__ = "2.0.0"

DEFAULT_SENSORS = "sensor_1:D4:DHT11:Sensor 1,sensor_2:D25:DHT11:Sensor 2"


def create_app(reader: SensorReader, device: dict[str, Any]) -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        alive = reader.is_alive()
        return jsonify(status="ok" if alive else "error"), 200 if alive else 503

    @app.get("/api/v1/sensors")
    def sensors():
        return jsonify(device=device, sensors=reader.snapshot())

    @app.get("/api/v1/sensors/<sensor_id>")
    def sensor(sensor_id: str):
        for item in reader.snapshot():
            if item["id"] == sensor_id:
                return jsonify(item)
        return jsonify(error="not_found"), 404

    return app


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sensors = parse_sensors(os.environ.get("SENSORS", DEFAULT_SENSORS))
    backend = FakeBackend() if os.environ.get("SENSOR_BACKEND", "dht") == "fake" else DhtBackend()
    reader = SensorReader(backend, sensors, interval=float(os.environ.get("READ_INTERVAL", "30")))
    device = {
        "id": os.environ.get("DEVICE_ID") or socket.gethostname(),
        "name": os.environ.get("DEVICE_NAME", "Environmental Monitoring"),
        "version": __version__,
    }

    # SIGTERM (docker stop) vira SystemExit para cair no finally e soltar o GPIO.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    reader.start()
    try:
        serve(create_app(reader, device), host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
    finally:
        reader.stop()
        backend.close()


if __name__ == "__main__":
    main()
