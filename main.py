from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.database import close_metadata_client, ensure_indexes
from middleware.basic_auth import BasicAuthMiddleware
from routes import api, pages

app = FastAPI(title="MongoDB Monitoring", version="0.1.0")
app.add_middleware(BasicAuthMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    ensure_indexes()


@app.on_event("shutdown")
def shutdown() -> None:
    close_metadata_client()
