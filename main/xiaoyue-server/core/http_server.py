import asyncio
from pathlib import Path
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.parent_handler import ParentConsoleHandler
from core.api.vision_handler import VisionHandler

TAG = __name__
PARENT_WEB_DIR = Path(__file__).resolve().parents[1] / "web" / "parent"


class SimpleHttpServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self.parent_handler = ParentConsoleHandler(config)

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        """获取websocket地址

        Args:
            local_ip: 本地IP地址
            port: 端口号

        Returns:
            str: websocket地址
        """
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaoyue/v1/"

    async def start(self):
        try:
            server_config = self.config["server"]
            read_config_from_api = self.config.get("read_config_from_api", False)
            host = server_config.get("ip", "0.0.0.0")
            port = int(server_config.get("http_port", 8003))

            if port:
                app = web.Application()

                if not read_config_from_api:
                    # 如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口，用于下发websocket接口
                    app.add_routes(
                        [
                            web.get("/xiaoyue/ota/", self.ota_handler.handle_get),
                            web.post("/xiaoyue/ota/", self.ota_handler.handle_post),
                            web.options(
                                "/xiaoyue/ota/", self.ota_handler.handle_options
                            ),
                            # 下载接口，仅提供 data/bin/*.bin 下载
                            web.get(
                                "/xiaoyue/ota/download/{filename}",
                                self.ota_handler.handle_download,
                            ),
                            web.options(
                                "/xiaoyue/ota/download/{filename}",
                                self.ota_handler.handle_options,
                            ),
                        ]
                    )
                app.add_routes(
                    [
                        web.get(
                            "/xiaoyue/parent/api/overview",
                            self.parent_handler.overview,
                        ),
                        web.get(
                            "/xiaoyue/parent/api/conversations",
                            self.parent_handler.conversations,
                        ),
                        web.post(
                            "/xiaoyue/parent/api/check-content",
                            self.parent_handler.check_content,
                        ),
                        web.get(
                            "/parent",
                            lambda _: web.HTTPFound("/parent/"),
                        ),
                        web.get(
                            "/parent/",
                            lambda _: web.FileResponse(
                                PARENT_WEB_DIR / "index.html"
                            ),
                        ),
                    ]
                )
                if PARENT_WEB_DIR.exists():
                    app.router.add_static(
                        "/parent/",
                        PARENT_WEB_DIR,
                        show_index=True,
                        follow_symlinks=False,
                    )
                # 添加路由
                app.add_routes(
                    [
                        web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                        web.post(
                            "/mcp/vision/explain", self.vision_handler.handle_post
                        ),
                        web.options(
                            "/mcp/vision/explain", self.vision_handler.handle_options
                        ),
                    ]
                )

                # 运行服务
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()

                # 保持服务运行
                while True:
                    await asyncio.sleep(3600)  # 每隔 1 小时检查一次
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"HTTP服务器启动失败: {e}")
            import traceback

            self.logger.bind(tag=TAG).error(f"错误堆栈: {traceback.format_exc()}")
            raise
