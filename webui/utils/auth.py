"""认证工具"""

from fastapi import HTTPException, Query, Request


async def verify_key(request: Request, key: str = Query(..., description="访问密钥")):
    """验证访问密钥

    Args:
        request: FastAPI 请求对象
        key: 访问密钥

    Raises:
        HTTPException: 密钥无效时抛出 401 错误
    """
    config = request.app.state.config
    webui_key = config.get("webui_key", "")

    if not webui_key:
        # 未配置密钥，允许访问
        return True

    if key != webui_key:
        raise HTTPException(status_code=401, detail="访问密钥无效")

    return True
