from __future__ import annotations
import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from core.config import get_settings
from db.database import create_tables, seed_admin
from routers.auth import router as auth_router
from routers.signals import router as signals_router
from routers.trade import router as trade_router
from routers.wallet import router as wallet_router
from routers.subscription import router as sub_router
from routers.admin import router as admin_router
from routers.telegram import router as tg_router
from routers.ai import router as ai_router
from routers.prices import router as prices_router
from routers.ws import router as ws_router
from services.telegram import TG

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s - %(message)s")
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("WhaleX Prime starting up")
    create_tables()
    seed_admin()
    await TG.setup()
    from radars.futures.service import start_all_services
    from radars.futures.position_manager import run_position_manager
    from routers.ws import registry
    async def _broadcast(data):
        await registry.broadcast(data)
    asyncio.create_task(start_all_services(broadcast_fn=_broadcast))
    asyncio.create_task(run_position_manager())
    from services.prices import start_price_stream
    asyncio.create_task(start_price_stream(), name="prices")
    log.info("WhaleX Prime ready")
    yield
    log.info("WhaleX Prime shutting down")

app = FastAPI(title="WhaleX Prime", version="1.0.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)
app.include_router(signals_router)
app.include_router(trade_router)
app.include_router(wallet_router)
app.include_router(sub_router)
app.include_router(admin_router)
app.include_router(tg_router)
app.include_router(ai_router)
app.include_router(prices_router)
app.include_router(ws_router)

@app.get("/", include_in_schema=False)
async def root(): return RedirectResponse("/static/index.html", 302)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "telegram": bool(settings.telegram_bot_token)}

app.mount("/static", StaticFiles(directory="/opt/whalex/static"), name="static")
