import subprocess
import os

class RtspServer:
    def __init__(self, path=None):
        # ruta absoluta del ejecutable
        self.path = path or os.path.abspath("./rtsp-server")
        self.server_process = None

    def start(self):
        if self.server_process:
            return

        if not os.path.exists(self.path):
            raise FileNotFoundError(f"No se encontró el ejecutable en: {self.path}")

        self.server_process = subprocess.Popen([self.path])
        print("MediaMTX iniciado")

    def stop(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
            print("MediaMTX detenido")


STREAM_SERVER = RtspServer()
