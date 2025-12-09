import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== 1. 修复导入路径 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ==================== 2. Mock astrbot ====================
# 创建独立的 mock 模块以解决 'is not a package' 问题
mock_astrbot = MagicMock()
mock_api = MagicMock()
mock_core = MagicMock()

# 将顶层包注册到 sys.modules
sys.modules["astrbot"] = mock_astrbot
sys.modules["astrbot.api"] = mock_api
sys.modules["astrbot.core"] = mock_core

# 模拟 astrbot.api 的子模块
mock_api_event = MagicMock()
mock_api_provider = MagicMock()
mock_api_star = MagicMock()
mock_api_message_components = MagicMock()
sys.modules["astrbot.api.event"] = mock_api_event
sys.modules["astrbot.api.provider"] = mock_api_provider
sys.modules["astrbot.api.star"] = mock_api_star
sys.modules["astrbot.api.message_components"] = mock_api_message_components

# 模拟 astrbot.core 的子模块
mock_core_message = MagicMock()
mock_core_message_event_result = MagicMock()
sys.modules["astrbot.core.message"] = mock_core_message
sys.modules["astrbot.core.message.message_event_result"] = (
    mock_core_message_event_result
)

# 在 mock 模块上设置预期的属性
mock_api.logger = MagicMock()
mock_api_event.AstrMessageEvent = MagicMock()
mock_api_provider.LLMResponse = MagicMock()
mock_api_provider.ProviderRequest = MagicMock()
mock_api_star.Context = MagicMock()
mock_core_message_event_result.MessageEventResult = MagicMock()

# ==================== 3. 导入业务代码 ====================
from core.command_handler import CommandHandler  # noqa: E402

# ==================== 4. 测试 Fixtures ====================


@pytest.fixture
def mock_service():
    """提供一个 mock 的 PluginService 对象。"""
    service = MagicMock()
    service.graph_engine = MagicMock()
    service.graph_engine.get_graph_statistics = AsyncMock()
    service.graph_engine.migrate_memories = AsyncMock()
    service.graph_engine.delete_node_by_id = AsyncMock()
    service.graph_engine.get_full_graph = AsyncMock()
    return service


@pytest.fixture
def mock_event():
    """提供一个 mock 的 AstrMessageEvent 对象。"""
    event = MagicMock()
    event.unified_msg_origin = "session_123"
    event.plain_result = MagicMock(side_effect=lambda x: x)
    return event


@pytest.fixture
def handler(mock_service):
    """提供一个 CommandHandler 实例。"""
    return CommandHandler(mock_service)


# ==================== 5. 辅助函数 ====================


async def get_async_generator_result(gen):
    """从异步生成器中获取所有结果。"""
    return [item async for item in gen]


# ==================== 6. 测试用例 ====================


@pytest.mark.asyncio
async def test_handle_stat_success(handler, mock_service, mock_event):
    """测试：成功获取并格式化图谱统计信息。"""
    # 准备
    stats = {"node_count": 100, "edge_count": 200}
    mock_service.graph_engine.get_graph_statistics.return_value = stats

    # 执行
    results = await get_async_generator_result(handler.handle_stat(mock_event))

    # 验证
    assert len(results) == 1
    assert "node_count: 100" in results[0]
    assert "edge_count: 200" in results[0]
    mock_service.graph_engine.get_graph_statistics.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stat_failure(handler, mock_service, mock_event):
    """测试：获取统计信息失败时返回错误消息。"""
    # 准备
    mock_service.graph_engine.get_graph_statistics.return_value = None

    # 执行
    results = await get_async_generator_result(handler.handle_stat(mock_event))

    # 验证
    assert results[0] == "获取图谱统计信息失败。"


@pytest.mark.asyncio
async def test_handle_link_session(handler, mock_service, mock_event):
    """测试：成功关联会话记忆。"""
    # 准备
    target_session_id = "session_456"
    mock_service.graph_engine.migrate_memories.return_value = 5

    # 执行
    results = await get_async_generator_result(
        handler.handle_link_session(mock_event, target_session_id)
    )

    # 验证
    assert "成功将 5 条记忆片段" in results[0]
    mock_service.graph_engine.migrate_memories.assert_called_once_with(
        "session_123", target_session_id
    )


@pytest.mark.asyncio
async def test_handle_link_session_to_self(handler, mock_event):
    """测试：不能将记忆关联到当前会话本身。"""
    # 准备
    target_session_id = "session_123"

    # 执行
    results = await get_async_generator_result(
        handler.handle_link_session(mock_event, target_session_id)
    )

    # 验证
    assert results[0] == "不能将记忆关联到同一会话。"


@pytest.mark.asyncio
async def test_handle_forget(handler, mock_service, mock_event):
    """测试：成功忘记一个实体。"""
    # 准备
    entity_name = "旧知识"
    mock_service.graph_engine.delete_node_by_id.return_value = True

    # 执行
    results = await get_async_generator_result(
        handler.handle_forget(mock_event, entity_name=entity_name)
    )

    # 验证
    assert f"已尝试忘记关于 '{entity_name}' 的记忆。" in results[0]
    mock_service.graph_engine.delete_node_by_id.assert_called_once_with(
        entity_name, "Entity"
    )


@pytest.mark.asyncio
async def test_handle_dump(handler, mock_service, mock_event):
    """测试：成功导出当前会话的图数据。"""
    # 准备
    graph_data = {"nodes": [{"id": "a"}], "edges": []}
    mock_service.graph_engine.get_full_graph.return_value = graph_data

    # 执行
    results = await get_async_generator_result(handler.handle_dump(mock_event))

    # 验证
    dumped_json = json.loads(results[0])
    assert dumped_json == graph_data
    mock_service.graph_engine.get_full_graph.assert_called_once_with("session_123")


@pytest.mark.asyncio
async def test_handle_migrate_v2(handler, mock_event):
    """测试：迁移指令返回废弃信息。"""
    # 执行
    results = await get_async_generator_result(handler.handle_migrate_v2(mock_event))

    # 验证
    assert "此功能已被废弃" in results[0]
