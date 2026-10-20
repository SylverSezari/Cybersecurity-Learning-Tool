from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import engine, get_db, init_db
from routers import accounts, chapters, exercises


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(exercises.router, prefix="/api/exercises", tags=["exercises"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])


# Web functions


## home
@app.get("/", include_in_schema=False, name="home")
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")


## login
@app.get("/login", include_in_schema=False, name="login_page")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"title": "Sign in"}
    )


## account management
@app.get("/account", include_in_schema=False, name="account_page")
async def account_page(request: Request):
    return templates.TemplateResponse(
        request, "account.html", {"title": "Account Management"}
    )


## chapter select
@app.get("/chapters", include_in_schema=False, name="chapters")
async def chapter_select(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Chapter).order_by(
            models.Chapter.active.desc(),
            models.Chapter.position,
            models.Chapter.id,
        )
    )

    chapters = result.scalars().all()

    return templates.TemplateResponse(
        request, "chapter_select.html", {"chapters": chapters, "title": "Chapter Select"}
    )
