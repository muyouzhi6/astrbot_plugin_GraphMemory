"""WebUI 管理器"""

import asyncio

from astrbot.api import logger


class WebUIManager:
    """WebUI 服务器管理器"""

    def __init__(self, manager, config: dict):
        self.manager = manager
        self.config = config
        self.server: any | None = None
        self.task: asyncio.Task | None = None

    async def start(self):
        """启动 WebUI 服务器"""
        try:
            import uvicorn

            from ..webui.app import create_app

            port = self.config.get("webui_port", 8081)
            host = "0.0.0.0"

            # 生成或获取访问密钥
            webui_key = self.config.get("webui_key", "")
            if not webui_key:
                import secrets
                webui_key = secrets.token_urlsafe(32)
                logger.info(f"[GraphMemory] WebUI 访问密钥: {webui_key}")
                logger.info("[GraphMemory] 请妥善保管此密钥，或在配置中设置 webui_key")

            # 创建 FastAPI 应用
            app = create_app(self.manager, self.config)

            # 创建 uvicorn 配置
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="info",
            )
            self.server = uvicorn.Server(config)

            # 在后台任务中运行服务器
            self.task = asyncio.create_task(self.server.serve())

            logger.info(f"[GraphMemory] WebUI 已启动: http://{host}:{port}")
            logger.info(f"[GraphMemory] 访问地址: http://localhost:{port}?key={webui_key}")

        except ImportError:
            logger.warning("[GraphMemory] 未安装 FastAPI 或 uvicorn，WebUI 功能不可用")
            logger.warning("[GraphMemory] 请运行: pip install fastapi uvicorn")
        except Exception as e:
            logger.error(f"[GraphMemory] WebUI 启动失败: {e}", exc_info=True)

    async def stop(self):
        """停止 WebUI 服务器"""
        if self.server:
            logger.info("[GraphMemory] 正在停止 WebUI 服务器...")
            self.server.should_exit = True

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("[GraphMemory] WebUI 服务器已停止")
