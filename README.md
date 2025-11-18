# CamFrame – Simulador de cámaras IP con FastAPI

## 1. Crear entorno virtual
python3 -m venv venv

## 2. Activar entorno
### Linux / Mac
source venv/bin/activate

### Windows
venv\Scripts\activate

## 3. Instalar dependencias
pip install -r requirements.txt

## 4. Ejecutar el servidor
uvicorn app.main:app --reload

## 5. index
POST http://localhost:8000/

Los videos se guardan en la carpeta /videos y su registro queda en SQLite.



## Inicio del servidor RTSP

Antes de iniciar la aplicación, es necesario ejecutar el servidor RTSP:

```bash
./rtsp-server
```
