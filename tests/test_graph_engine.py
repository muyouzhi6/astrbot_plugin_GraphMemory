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

    # 强制使用正斜杠路径
    db_path = os.path.join(temp_dir_path, "adv_graph_db").replace("\\", "/")

    ge = GraphEngine(db_path=db_path)
    yield ge
    try:
        ge.close()
    except Exception:
        pass
    temp_dir_obj.cleanup()


# ==================== 复杂场景测试 ====================


def test_persona_isolation_same_session(engine):
    """
    测试：同一个会话中，不同人格（Persona）的记忆隔离。
    场景：在群 A 中，人格 'User' 认为 Python 简单，人格 'Coder' 认为 Python 复杂。
    """
    sid = "group_1"

    # 写入数据
    engine.add_triplet("Python", "status", "Easy", sid, persona_id="User")
    engine.add_triplet("Python", "status", "Complex", sid, persona_id="Coder")

    # 检索 'User' 人格
    res_user = engine.search_subgraph(["Python"], sid, persona_id="User")
    assert "Easy" in res_user
    assert "Complex" not in res_user

    # 检索 'Coder' 人格
    res_coder = engine.search_subgraph(["Python"], sid, persona_id="Coder")
    assert "Complex" in res_coder
    assert "Easy" not in res_coder


def test_cycles_and_self_loops(engine):
    """
    测试：图中的环路和自环。
    验证 BFS 是否会死循环，或者能否正确处理自己指向自己的关系。
    """
    sid = "logic_test"
    pid = "p1"

    # 1. 自环: Ouroboros eats Ouroboros
    engine.add_triplet("Ouroboros", "eats", "Ouroboros", sid, pid)

    res_self = engine.search_subgraph(["Ouroboros"], sid, pid, hops=2)
    assert "(Ouroboros) --[eats]--> (Ouroboros)" in res_self

    # 2. 互斥环: A -> hates -> B, B -> hates -> A
    engine.add_triplet("Cat", "hates", "Dog", sid, pid)
    engine.add_triplet("Dog", "hates", "Cat", sid, pid)

    res_cycle = engine.search_subgraph(["Cat"], sid, pid, hops=3)
    assert "(Cat) --[hates]--> (Dog)" in res_cycle
    assert "(Dog) --[hates]--> (Cat)" in res_cycle
    # 确保没有报错或超时


def test_partial_match_search(engine):
    """
    测试：模糊匹配 / 子串匹配。
    """
    sid = "fuzzy_test"
    pid = "p1"

    # 存入全名
    engine.add_triplet("AstrBot Project", "is_written_in", "Python", sid, pid)

    # 搜索部分关键词 "Astr"
    res = engine.search_subgraph(["Astr"], sid, pid)
    assert "Python" in res
    assert "AstrBot Project" in res


def test_clear_context(engine):
    """
    测试：清除特定上下文记忆。
    """
    sid = "trash_session"
    pid = "p1"

    engine.add_triplet("Trash", "is", "Garbage", sid, pid)
    assert "Garbage" in engine.search_subgraph(["Trash"], sid, pid)

    # 执行清理
    engine.clear_context(sid, pid)

    # 再次搜索应为空
    assert engine.search_subgraph(["Trash"], sid, pid) == ""

    # 确保没有误删其他 Session 的数据
    other_sid = "safe_session"
    engine.add_triplet("Treasure", "is", "Gold", other_sid, pid)
    engine.clear_context(sid, pid)  # 再次清理 sid
    assert "Gold" in engine.search_subgraph(["Treasure"], other_sid, pid)


def test_dense_graph_traversal(engine):
    """
    测试：稍复杂的密集连接（星型结构）。
    CentralNode 连接了 Leaf1...Leaf5，验证能否一次性召回。
    """
    sid = "star_graph"
    pid = "p1"

    center = "Sun"
    planets = ["Mercury", "Venus", "Earth", "Mars", "Jupiter"]

    for p in planets:
        engine.add_triplet(center, "orbited_by", p, sid, pid)

    # 搜索 Sun
    res = engine.search_subgraph([center], sid, pid, hops=1)

    # 验证所有行星都在结果中
    for p in planets:
        assert p in res
    assert "orbited_by" in res


def test_persona_migration(engine):
    """
    测试：只迁移 Session，但保持 Persona ID 不变，或反之。
    """
    old_sid, new_sid = "chat_old", "chat_new"
    old_pid, new_pid = "maid", "butler"

    # 场景 1: Session 变了，Persona 没变 (例如 Bot 被拉到了新群，但还是那个性格)
    engine.add_triplet("Master", "orders", "Tea", old_sid, old_pid)

    engine.migrate(
        from_context={"session_id": old_sid, "persona_id": old_pid},
        to_context={"session_id": new_sid, "persona_id": old_pid},  # PID 保持 maid
    )

    res = engine.search_subgraph(["Master"], new_sid, old_pid)
    assert "Tea" in res

    # 场景 2: Session 没变，Persona 变了 (例如原地切换人格)
    engine.add_triplet(
        "Master", "orders", "Coffee", old_sid, old_pid
    )  # 此时 old_sid 已经空了(被迁移走了)，重新加一条

    engine.migrate(
        from_context={"session_id": old_sid, "persona_id": old_pid},
        to_context={"session_id": old_sid, "persona_id": new_pid},  # SID 保持 chat_old
    )

    res = engine.search_subgraph(["Master"], old_sid, new_pid)
    assert "Coffee" in res
