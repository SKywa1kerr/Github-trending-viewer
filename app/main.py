import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import init_db, is_db_empty
from app.routers import projects, keywords, system, favorites

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from app.scheduler import start_scheduler, stop_scheduler
    from app.state_store import set_runtime_state
    from app.translator import reset_processing_translations, start_translation_worker

    set_runtime_state(
        is_refreshing="0",
        refresh_stage="",
        refresh_detail="",
        progress_total="0",
        progress_done="0",
        translation_worker_running="0",
    )
    reset_processing_translations()
    start_scheduler()
    if is_db_empty():
        from app.routers.system import _do_refresh

        asyncio.create_task(_do_refresh())
    else:
        start_translation_worker()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="GitHub Trending Viewer", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(keywords.router)
app.include_router(system.router)
app.include_router(favorites.router)




# 静态文件托管 — 必须放在所有路由注册之后
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
