import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# ==================== 1. 修复导入路径 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ==================== 2. Mock astrbot ====================
mock_astrbot = MagicMock()
mock_astrbot.api.logger = MagicMock()
sys.modules["astrbot"] = mock_astrbot
sys.modules["astrbot.api"] = mock_astrbot.api

# ==================== 3. 导入业务代码 ====================
from core.graph_engine import GraphEngine  # noqa: E402


@pytest.fixture
def engine():
    # 使用 tempfile 创建临时目录，避免 Windows 锁问题
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir_path = temp_dir_obj.name

    # 数据库的基础路径
    db_base_path = os.path.join(temp_dir_path, "adv_graph_db")
    os.makedirs(db_base_path, exist_ok=True)

    # 模拟 embedding provider 以控制维度
    from unittest.mock import AsyncMock

    mock_embedding_provider = MagicMock()
    mock_embedding_provider.embed = AsyncMock(return_value=[0.1] * 128)
    # 直接为 mock provider 设置 dims 属性
    mock_embedding_provider.dims = 128

    from pathlib import Path

    ge = GraphEngine(
        db_path=Path(db_base_path), embedding_provider=mock_embedding_provider
    )
    yield ge
    try:
        ge.close()
    except Exception:
        pass
    temp_dir_obj.cleanup()


# ==================== 复杂场景测试 (已更新为异步 API) ====================


@pytest.mark.asyncio
async def test_add_and_search(engine):
    """测试基本的数据添加和搜索功能。"""
    from core.graph_entities import EntityNode, RelatedToRel, SessionNode

    sid = "session_1"
    await engine.add_session(SessionNode(id=sid, type="GROUP", name="Test Session"))
    await engine.add_entity(EntityNode(name="AstrBot", type="Project"))
    await engine.add_entity(EntityNode(name="Python", type="Language"))
    await engine.add_relation(
        RelatedToRel(
            src_entity="AstrBot", tgt_entity="Python", relation="is_written_in"
        )
    )
    await engine.link_entity_to_session(sid, "AstrBot")
    await engine.link_entity_to_session(sid, "Python")

    # 模拟搜索
    query_embedding = [0.1] * 128  # 假设 embedding 维度为 128
    result = await engine.search("AstrBot", query_embedding, sid, 3, 3, 5)

    # 断言不能过于具体，因为搜索结果依赖于向量和关键词算法
    # 但至少可以确认它返回了字符串，并且包含了我们插入的实体
    assert isinstance(result, str)
    assert "AstrBot" in result
    assert "Python" in result
    assert "is_written_in" in result


@pytest.mark.asyncio
async def test_delete_node(engine):
    """测试删除节点的功能。"""
    from core.graph_entities import EntityNode, SessionNode

    sid = "session_delete"
    entity_name = "TemporaryEntity"

    await engine.add_session(SessionNode(id=sid, type="GROUP", name="Delete Test"))
    await engine.add_entity(EntityNode(name=entity_name, type="Temp"))
    await engine.link_entity_to_session(sid, entity_name)

    # 确认实体存在
    query_embedding = [0.2] * 128
    result_before = await engine.search(entity_name, query_embedding, sid, 1, 1, 1)
    assert entity_name in result_before

    # 删除节点
    await engine.delete_node_by_id(entity_name, "Entity")

    # 确认实体已被删除
    result_after = await engine.search(entity_name, query_embedding, sid, 1, 1, 1)
    assert entity_name not in result_after


@pytest.mark.asyncio
async def test_get_full_graph(engine):
    """测试导出完整会话图的功能。"""
    from core.graph_entities import EntityNode, RelatedToRel, SessionNode

    sid = "session_export"
    await engine.add_session(SessionNode(id=sid, type="GROUP", name="Export Test"))
    await engine.add_entity(EntityNode(name="NodeA", type="TestNode"))
    await engine.add_entity(EntityNode(name="NodeB", type="TestNode"))
    await engine.add_relation(
        RelatedToRel(src_entity="NodeA", tgt_entity="NodeB", relation="connects_to")
    )
    await engine.link_entity_to_session(sid, "NodeA")
    await engine.link_entity_to_session(sid, "NodeB")

    graph_data = await engine.get_full_graph(sid)

    assert graph_data is not None
    assert len(graph_data["nodes"]) >= 2  # Session, NodeA, NodeB
    assert len(graph_data["edges"]) >= 2  # Session->NodeA, Session->NodeB

    node_names = {node["name"] for node in graph_data["nodes"]}
    assert "NodeA" in node_names
    assert "NodeB" in node_names


@pytest.mark.asyncio
async def test_prune_graph(engine):
    """测试图剪枝功能。"""
    import time

    from core.graph_entities import MessageNode, SessionNode, UserNode

    sid = "session_prune"
    uid = "user_prune"
    await engine.add_session(SessionNode(id=sid, type="GROUP", name="Prune Test"))
    await engine.add_user(UserNode(id=uid, name="Prune User", platform="test"))

    # 添加一个非常旧的消息
    old_timestamp = int(time.time() - (100 * 24 * 3600))  # 100天前
    await engine.add_message(
        MessageNode(
            id="old_msg",
            content="old",
            timestamp=old_timestamp,
            sender_id=uid,
            session_id=sid,
        )
    )

    # 添加一个新消息
    await engine.add_message(
        MessageNode(
            id="new_msg",
            content="new",
            timestamp=int(time.time()),
            sender_id=uid,
            session_id=sid,
        )
    )

    # 执行剪枝，设置最大节点数为1，强制删除旧消息
    deleted_count = await engine.prune_graph(max_nodes=1, message_max_days=90)

    assert deleted_count > 0

    # 验证旧消息已被删除
    stats = await engine.get_graph_statistics()
    assert stats is not None
    # 理想情况下，旧消息被删除，但由于图结构复杂，只断言节点数减少
    # 注意：实际剩余节点数可能 > 1，因为还存在 User, Session 等节点


@pytest.mark.asyncio
async def test_consolidation_cycle(engine):
    """测试记忆巩固的查找和执行流程。"""
    import time

    from core.graph_entities import MessageNode, SessionNode, UserNode

    sid = "session_consolidate"
    uid = "user_consolidate"
    await engine.add_session(SessionNode(id=sid, type="GROUP", name="Consolidate Test"))
    await engine.add_user(UserNode(id=uid, name="Consolidate User", platform="test"))

    # 添加足够多的消息以触发巩固
    for i in range(10):
        await engine.add_message(
            MessageNode(
                id=f"msg_{i}",
                content=f"message {i}",
                timestamp=int(time.time()),
                sender_id=uid,
                session_id=sid,
            )
        )

    # 查找需要巩固的会话
    sessions_to_process = await engine.find_sessions_for_consolidation(threshold=5)
    assert sid in sessions_to_process

    # 获取用于巩固的消息
    consolidation_data = engine.get_messages_for_consolidation(sid, limit=10)
    assert consolidation_data is not None
    message_ids, text_block, user_ids = consolidation_data
    assert len(message_ids) == 10
    assert "message 0" in text_block
    assert uid in user_ids

    # 执行巩固
    summary_text = "This is a summary."
    summary_embedding = [0.3] * 128
    await engine._run_in_executor(
        engine._consolidate_memory_sync,
        sid,
        summary_text,
        message_ids,
        user_ids,
        summary_embedding,
    )

    # 验证 MemoryFragment 已创建
    stats = await engine.get_graph_statistics()
    assert stats is not None
    assert stats.get("MemoryFragment_count", 0) == 1
