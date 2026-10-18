from pathlib import Path

# Imported so the ORM metadata is registered before create_all runs on startup.
import models.models  # noqa: F401
from core.database import Base, engine
from core.exceptions import AppError
from routers.routers import outlet_router, personnel_router, router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


async def Lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="My FastAPI Project",
    description="API documentation with a custom dark theme",
    version="1.0.0",
    lifespan=Lifespan,
    docs_url=None,
)

# Allow the Next.js dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the static directory if it doesn't exist
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

# Serve static CSS files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    swagger_html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    )

    html_content = swagger_html.body.decode("utf-8")

    # Load custom dark theme CSS
    html_content = html_content.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/swagger-dark.css"></head>',
    )

    return HTMLResponse(content=html_content)


@app.get("/")
async def home():
    return "hello world"


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


app.include_router(router)
app.include_router(outlet_router)
app.include_router(personnel_router)
