import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db, is_db_empty
from app.routers import projects, keywords, system

app = FastAPI(title="GitHub Trending Viewer")

app.include_router(projects.router)
app.include_router(keywords.router)
app.include_router(system.router)


@app.on_event("startup")
async def startup():
    init_db()
    from app.scheduler import start_scheduler
    start_scheduler()
    if is_db_empty():
        from app.routers.system import _do_refresh
        asyncio.create_task(_do_refresh())


# 静态文件托管 — 必须放在所有路由注册之后
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
