import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(__file__))

from db import get_db, stop_tunnel
from routers import products, floor_plans, placements


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작: DB 연결 확인
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM product")
        count = cur.fetchone()["cnt"]
        print(f"[startup] PostgreSQL connected - product {count} rows")

        cur.execute("SELECT COUNT(*) AS cnt FROM floor_plan")
        fp_count = cur.fetchone()["cnt"]
        print(f"[startup] floor_plan {fp_count} rows")

    yield

    # 종료: SSH 터널 정리
    stop_tunnel()


app = FastAPI(title="Home Appliance Placement Simulator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(floor_plans.router)
app.include_router(placements.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
