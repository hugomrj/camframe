from sqlmodel import SQLModel, Field
import uuid

class Video(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    ruta: str            # URL pública
    archivo_fisico: str  # ruta en disco
    stream_key: str
