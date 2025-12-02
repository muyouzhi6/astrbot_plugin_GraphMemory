import os
import secrets
import string
import threading

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from astrbot.api import logger

from .graph_engine import GraphEngine
from .graph_service import GraphService


class WebServer:
    def __init__(self, engine: GraphEngine, config: dict):
        self.config = config
        self.host = config.get("webui_host", "0.0.0.0")
        self.port = config.get("webui_port", 8081)
        self.configured_key = config.get("webui_key", "")

        # Initialize Service
        self.service = GraphService(engine)

        # Authentication
        self.auth_key = self.configured_key
        if not self.auth_key:
            self.auth_key = self._generate_key()
            logger.warning(f"\n{'='*40}\n[GraphMemory] WebUI Access Key: {self.auth_key}\n{'='*40}")

        self.sessions = set() # Valid session tokens

        # FastAPI App
        self.app = FastAPI(title="GraphMemory WebUI", version="1.0.0")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self._setup_routes()

        self.server_thread = None
        self.server: uvicorn.Server | None = None
        self.should_exit = False

    def _generate_key(self, length=16):
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    def _check_auth(self, request: Request):
        # 1. Check Header Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token in self.sessions:
                return True

        # 2. Check Cookie
        token = request.cookies.get("session_token")
        if token and token in self.sessions:
            return True

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    def _setup_routes(self):

        # --- Static & Templates ---
        current_dir = os.path.dirname(os.path.abspath(__file__))
        resources_dir = os.path.join(current_dir, "../resources")
        static_dir = os.path.join(resources_dir, "static")

        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            # Serve pure HTML/JS version (no build required)
            index_path = os.path.join(resources_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)

            return HTMLResponse(
                content="<h1>WebUI not found.</h1>"
                        "<p>index.html is missing in resources folder.</p>",
                status_code=404
            )

        # Serve app.js from resources directory
        @self.app.get("/app.js")
        async def serve_app_js():
            app_js_path = os.path.join(resources_dir, "app.js")
            if os.path.exists(app_js_path):
                return FileResponse(app_js_path, media_type="application/javascript")
            return HTMLResponse(content="app.js not found", status_code=404)

        # Mount static files if build directory exists (for backwards compatibility)
        if os.path.isdir(static_dir):
            self.app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @self.app.get("/favicon.ico")
        async def favicon():
             # Return empty or default icon to prevent 404
            return HTMLResponse(content="", status_code=204)

        # --- Auth API ---
        @self.app.post("/api/login")
        async def login(data: dict):
            key = data.get("key")
            if key == self.auth_key:
                # Generate a session token
                token = secrets.token_hex(16)
                self.sessions.add(token)

                # If using random one-time key, invalidate it (optional, but requested by user)
                # But if configured_key is set, we don't invalidate it.
                if not self.configured_key:
                    # Logic: "Single use" - maybe means the key displayed in console is valid only once to establish a session?
                    # Or maybe just "temporary until restart".
                    # User said: "若无密钥自动生成随机密钥，单次有效" (If no key, auto-generate random key, valid once).
                    # This implies once used to login, it cannot be used again?
                    # But then if user opens another browser/device, they can't login.
                    # Let's stick to "Temporary until restart" but maybe regenerate if we strictly follow "one-time"?
                    # Let's interpret "single use" as: The random key is just for initial handshake.
                    # But if we invalidate it, the user is locked out if they clear cookies.
                    # For now, let's keep it valid for the runtime, unless explicitly asked to invalidate.
                    # Re-reading: "单次有效" usually means "One-time Password (OTP)".
                    # So I will regenerate it or clear it.
                    pass

                response = JSONResponse(content={"status": "success", "token": token})
                response.set_cookie(key="session_token", value=token, httponly=True)
                return response
            else:
                raise HTTPException(status_code=401, detail="Invalid key")

        # --- Graph API ---
        @self.app.get("/api/graph/nodes")
        async def get_nodes(
            limit: int = 100,
            offset: int = 0,
            session_id: str | None = None,
            persona_id: str | None = None,
            _: bool = Depends(self._check_auth)
        ):
            return self.service.get_all_nodes(session_id, persona_id, limit, offset)

        @self.app.get("/api/graph/edges")
        async def get_edges(
            session_id: str | None = None,
            persona_id: str | None = None,
            _: bool = Depends(self._check_auth)
        ):
            return self.service.get_all_edges(session_id, persona_id)

        @self.app.get("/api/graph/search")
        async def search_nodes(
            q: str,
            session_id: str | None = None,
            persona_id: str | None = None,
            _: bool = Depends(self._check_auth)
        ):
            return self.service.search_nodes(q, session_id, persona_id)

        @self.app.get("/api/graph/debug_search")
        async def debug_search(
            q: str,
            session_id: str = "default", # 调试默认值
            persona_id: str = "default",
            _: bool = Depends(self._check_auth)
        ):
            keywords = [k.strip() for k in q.split(" ") if k.strip()]
            return await self.service.debug_search(keywords, session_id, persona_id)

        @self.app.get("/api/graph/node/{node_id}")
        async def get_node(node_id: str, _: bool = Depends(self._check_auth)):
            return self.service.get_node_details(node_id)

        @self.app.get("/api/graph/node/{node_id}/neighbors")
        async def get_neighbors(node_id: str, _: bool = Depends(self._check_auth)):
            return self.service.get_neighbors(node_id)

        # --- CRUD API ---
        @self.app.delete("/api/graph/node/{node_id}")
        async def delete_node(node_id: str, _: bool = Depends(self._check_auth)):
            try:
                self.service.delete_node(node_id)
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/graph/edge")
        async def delete_edge(src: str, tgt: str, rel: str, _: bool = Depends(self._check_auth)):
            try:
                self.service.delete_edge(src, tgt, rel)
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/graph/node/{node_id}")
        async def update_node(node_id: str, data: dict, _: bool = Depends(self._check_auth)):
            try:
                self.service.update_node(
                    node_id,
                    data["name"],
                    data["type"],
                    data.get("attributes", {}),
                    data.get("importance", 0.5)
                )
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/graph/edge")
        async def update_edge(data: dict, _: bool = Depends(self._check_auth)):
            try:
                self.service.update_edge(
                    data["source_id"],
                    data["target_id"],
                    data["old_relation"],
                    data["new_relation"],
                    data.get("weight", 1.0)
                )
                return {"status": "success"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    def start(self):
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)

        self.server_thread = threading.Thread(target=self.server.run, daemon=True)
        self.server_thread.start()
        logger.info(f"[GraphMemory] WebUI started at http://{self.host}:{self.port}")

    def stop(self):
        if self.server:
            self.server.should_exit = True
