from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from socketio import ASGIApp
import os

from .database import engine
from .models import Base

from .routes.auth_routes          import router as auth_router
from .routes.project_routes       import router as project_router
from .routes.review_routes        import router as review_router
from .routes.chats_routes         import router as chats_router
from .routes.version_routes       import router as version_router
from .routes.dashboard_routes     import router as dashboard_router
from .routes.admin_routes         import router as admin_router
from .routes.collaborator_routes  import router as collaborator_routes
from .routes.chatbot_routes       import router as chatbot_router

from .websocket.socket_manager import sio

Base.metadata.create_all(bind=engine)

fastapi_app = FastAPI(title="AI Code Review Platform")

fastapi_app.include_router(auth_router,          prefix="/auth",          tags=["Auth"])
fastapi_app.include_router(project_router,       prefix="/projects",      tags=["Projects"])
fastapi_app.include_router(review_router,        prefix="/review",        tags=["Review"])
fastapi_app.include_router(chats_router, prefix="/collaboration", tags=["Chats"])
fastapi_app.include_router(version_router,       prefix="/version",       tags=["Version"])
fastapi_app.include_router(dashboard_router,     prefix="/dashboard-api", tags=["Dashboard"])
fastapi_app.include_router(admin_router,         prefix="/admin-api",     tags=["Admin"])
fastapi_app.include_router(collaborator_routes,  prefix="/collab-api",    tags=["Collaborators"])
fastapi_app.include_router(chatbot_router,       prefix="/chatbot",       tags=["Chatbot"])

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

fastapi_app.mount("/css",    StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")),    name="css")
fastapi_app.mount("/js",     StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")),     name="js")

@fastapi_app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))

@fastapi_app.get("/register")
@fastapi_app.get("/register.html")
def register_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))

@fastapi_app.get("/login")
@fastapi_app.get("/login.html")
def login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@fastapi_app.get("/dashboard")
@fastapi_app.get("/index.html")
def dashboard_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@fastapi_app.get("/admin")
@fastapi_app.get("/admin.html")
def admin_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))


@fastapi_app.get("/project/{project_id}/chat")
def chat_room_page(project_id: int):
    return FileResponse(os.path.join(FRONTEND_DIR, "chat.html"))

@fastapi_app.get("/project/{project_id}/chatbot")
def chatbot_room_page(project_id: int):
    return FileResponse(os.path.join(FRONTEND_DIR, "chatbot.html"))

@fastapi_app.get("/chat/project/{project_id}")
def chat_room_redirect(project_id: int):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/project/{project_id}/chat", status_code=301)

app = ASGIApp(sio, other_asgi_app=fastapi_app)
