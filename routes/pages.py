from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/monitors/new", response_class=HTMLResponse, include_in_schema=False)
def new_monitor_page(request: Request):
    return templates.TemplateResponse(request, "monitor_new.html")


@router.get(
    "/monitors/{monitor_id}/storage",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def monitor_storage_page(
    request: Request, monitor_id: str, database_name: str | None = None
):
    template = (
        "monitor_collection_stats.html"
        if database_name
        else "monitor_database_stats.html"
    )
    return templates.TemplateResponse(
        request,
        template,
        {"monitor_id": monitor_id, "database_name": database_name},
    )


@router.get(
    "/monitors/{monitor_id}/current-ops",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def monitor_current_ops_page(request: Request, monitor_id: str):
    return templates.TemplateResponse(
        request, "monitor_current_ops.html", {"monitor_id": monitor_id}
    )


@router.get(
    "/monitors/{monitor_id}", response_class=HTMLResponse, include_in_schema=False
)
def monitor_page(request: Request, monitor_id: str):
    return templates.TemplateResponse(
        request, "monitor_detail.html", {"monitor_id": monitor_id}
    )
