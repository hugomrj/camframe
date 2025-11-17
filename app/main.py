from fastapi import FastAPI

from starlette.staticfiles import StaticFiles
from app.database import create_db_and_tables
from app.routes import router

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="videos"), name="media")

app.include_router(router)
