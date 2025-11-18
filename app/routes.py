from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi import Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse

from sqlmodel import Session, select
import subprocess
import os

from .models import Video
from .database import get_session
from app.services.stream_manager import STREAMER



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
        videos.append({
            "id": v.id,
            "nombre": v.nombre,
            "ruta": v.ruta,
            "stream_key": v.stream_key,
            "is_streaming": STREAMER.is_running(v.id),
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