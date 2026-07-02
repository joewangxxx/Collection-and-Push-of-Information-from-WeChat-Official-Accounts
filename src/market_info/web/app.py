from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from market_info.web.routes import articles, dashboard, jobs, reports
from market_info.web.templating import STATIC_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="Market Info Ops")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(articles.router)
    app.include_router(reports.router)
    return app
