from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from market_info.config import Settings
from market_info.web.routes import (
    accounts,
    articles,
    dashboard,
    delivery,
    jobs,
    projects,
    quality,
    reports,
    reviews,
)
from market_info.web.security import install_access_guard
from market_info.web.templating import STATIC_DIR


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Market Info Ops")
    install_access_guard(app, settings.web_access_token)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(dashboard.router)
    app.include_router(jobs.router)
    app.include_router(accounts.router)
    app.include_router(delivery.router)
    app.include_router(articles.router)
    app.include_router(reports.router)
    app.include_router(reviews.router)
    app.include_router(projects.router)
    app.include_router(quality.router)
    return app
