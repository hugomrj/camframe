import logging
import time
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi import Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, WebSocket, WebSocketDisconnect


from sqlmodel import Session, select
import subprocess
import os

from .models import Video
from .database import get_session
from app.services.stream_manager import STREAMER
from app.services import yolo_processor


router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Carpeta real donde se guardan los videos (fuera de /app)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # /project/app -> /project
UPLOAD_DIR = os.path.join(BASE_DIR, "videos")

os.makedirs(UPLOAD_DIR, exist_ok=True)




@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    videos_db = session.exec(select(Video)).all()

    videos = []
    for v in videos_db:
        stream_id = f"video{v.id}"
        
        # 🆕 Debug completo del estado
        is_yolo_active = yolo_processor.is_yolo_stream_active(stream_id)
        logger.info(f"🔍 Estado completo para {stream_id}:")
        logger.info(f"   - is_yolo_active: {is_yolo_active}")
        logger.info(f"   - active_streams: {stream_id in yolo_processor.active_streams}")
        logger.info(f"   - stream_tasks: {stream_id in yolo_processor.stream_tasks}")
        if stream_id in yolo_processor.stream_tasks:
            task = yolo_processor.stream_tasks[stream_id]
            logger.info(f"   - task done: {task.done()}")
        
        videos.append({
            "id": v.id,
            "nombre": v.nombre,
            "ruta": v.ruta,
            "stream_key": v.stream_key,
            "is_streaming": STREAMER.is_running(v.id),
            "is_yolo_active": is_yolo_active
        })

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "videos": videos}
    )




@router.get("/upload")
async def form_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload")
async def upload_video(
    nombre: str = Form(...),
    file: UploadFile = File(...),
    session=Depends(get_session)
):
    nombre = nombre.strip().replace(" ", "_")

    filename = f"{nombre}.mp4"
    file_path = os.path.join(UPLOAD_DIR, filename)

    # guardar el archivo físicamente
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # IMPORTANTE: guardar URL pública + ruta física real
    video = Video(
        nombre=nombre,
        ruta=f"/media/{filename}",         # URL pública
        archivo_fisico=file_path,          # archivo en disco (campo nuevo ideal)
        stream_key=nombre
    )

    session.add(video)
    session.commit()
    session.refresh(video)

    return RedirectResponse(url="/", status_code=303)





@router.get("/stream/start/{video_id}")
def start_stream(video_id: int, session=Depends(get_session)):
    video = session.exec(select(Video).where(Video.id == video_id)).first()
    if not video:
        return {"error": "Video no encontrado"}

    STREAMER.start_stream(video_id, video.archivo_fisico)
    return RedirectResponse(url="/", status_code=303)


@router.get("/stream/stop/{video_id}")
def stop_stream(video_id: int):
    STREAMER.stop_stream(video_id)
    return RedirectResponse(url="/", status_code=303)








logger = logging.getLogger(__name__)

# ==================== RUTAS YOLO ====================

@router.get("/yolo")
async def yolo_home(request: Request):
    """Página principal de YOLO"""
    return templates.TemplateResponse("yolo_index.html", {"request": request})

@router.post("/yolo/start/{video_id}")
async def start_yolo_stream(video_id: int):
    """Inicia procesamiento YOLO para un video"""
    # Verificar que el stream normal está activo
    if not STREAMER.is_running(video_id):
        return {"error": "Primero inicia el stream normal"}
    
    # RTSP URL del stream normal
    rtsp_url = f"rtsp://localhost:8554/video{video_id}"
    stream_id = f"video{video_id}"
    
    # Iniciar procesamiento YOLO
    success = await yolo_processor.start_yolo_stream(stream_id, rtsp_url)
    
    if success:
        return {
            "status": "YOLO stream iniciado",
            "stream_id": stream_id,
            "rtsp_url": rtsp_url
        }
    else:
        return {"error": "No se pudo iniciar YOLO stream"}
    


@router.get("/yolo/start/{video_id}")  # 🆕 Cambia POST por GET
async def start_yolo_stream(video_id: int, session: Session = Depends(get_session)):
    """Inicia procesamiento YOLO para un video"""
    if not STREAMER.is_running(video_id):
        return {"error": "Primero inicia el stream normal"}
    
    # RTSP URL del stream normal
    rtsp_url = f"rtsp://localhost:8554/video{video_id}"
    stream_id = f"video{video_id}"
    
    # Iniciar procesamiento YOLO
    success = await yolo_processor.start_yolo_stream(stream_id, rtsp_url)
    
    if success:
        # 🆕 Redirigir a la página principal para ver el estado actualizado
        return RedirectResponse(url="/", status_code=303)
    else:
        return {"error": "No se pudo iniciar YOLO stream"}


@router.websocket("/yolo/ws/{video_id}")
async def yolo_websocket_endpoint(websocket: WebSocket, video_id: int):
    """WebSocket para recibir frames con detecciones YOLO"""
    stream_id = f"video{video_id}"
    
    await websocket.accept()
    
    # Verificar que el stream YOLO está activo
    if not yolo_processor.is_yolo_stream_active(stream_id):
        await websocket.close(code=1000, reason="YOLO stream no activo")
        return
    
    # Agregar cliente al stream
    await yolo_processor.add_websocket_client(stream_id, websocket)
    
    try:
        while True:
            # Mantener conexión activa
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        logger.info(f"Cliente WebSocket desconectado de {stream_id}")
    finally:
        await yolo_processor.remove_websocket_client(stream_id, websocket)

@router.get("/yolo/player/{video_id}")
async def yolo_player(request: Request, video_id: int):
    """Reproductor para stream con YOLO"""
    stream_id = f"video{video_id}"
    
    if not yolo_processor.is_yolo_stream_active(stream_id):
        return {"error": "YOLO stream no activo"}
    
    return templates.TemplateResponse("yolo_player.html", {
        "request": request,
        "video_id": video_id,
        "stream_id": stream_id
    })

@router.post("/yolo/stop/{video_id}")
async def stop_yolo_stream(video_id: int):
    """Detiene el procesamiento YOLO"""
    stream_id = f"video{video_id}"
    await yolo_processor.stop_yolo_stream(stream_id)
    return {"status": "YOLO stream detenido", "video_id": video_id}