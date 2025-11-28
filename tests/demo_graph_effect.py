import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock

# --- 环境 Mock ---
# 获取当前脚本所在目录 (tests)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录 (tests 的上一级)
project_root = os.path.dirname(current_dir)

# 将项目根目录加入 python 搜索路径，这样才能找到 'core'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 临时 Mock astrbot，因为 core 依赖它
mock_astrbot = MagicMock()
mock_astrbot.api.logger = MagicMock()
# 让 logger 打印到控制台，方便我们看日志
mock_astrbot.api.logger.info = lambda x: print(f"[\033[94mINFO\033[0m] {x}")
mock_astrbot.api.logger.error = lambda x: print(f"[\033[91mERROR\033[0m] {x}")
sys.modules["astrbot"] = mock_astrbot
sys.modules["astrbot.api"] = mock_astrbot.api

from core.graph_engine import GraphEngine  # noqa: E402


def print_box(title, content):
    print(f"\n{'=' * 20} {title} {'=' * 20}")
    print(content.strip() if content else "[No Data]")
    print(f"{'=' * 50}\n")


def demo_scenario():
    # 1. 创建环境
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "demo_db").replace("\\", "/")
    print(f"[*] 初始化图数据库于: {db_path}")

    engine = GraphEngine(db_path=db_path)

    # 定义会话ID和人格ID
    sid = "session_侦探游戏"
    pid = "旁白"

    # 2. 模拟：输入一段中文剧情（存入三元组）
    print("[*] 正在注入剧情记忆...")

    story_triplets = [
        ("侦探", "调查", "案发现场", {}),
        ("案发现场", "包含", "带血的刀", {}),
        ("带血的刀", "有指纹", "嫌疑人Alex", {"置信度": 0.9}),
        ("嫌疑人Alex", "是仇人", "受害者Bob", {}),
        ("受害者Bob", "被发现于", "案发现场", {}),
        ("目击者C", "看见", "嫌疑人Alex", {"时间": "22:00"}),
    ]

    for src, rel, tgt, attr in story_triplets:
        engine.add_triplet(src, rel, tgt, sid, pid, attributes=attr)
        print(f"    + 已添加: ({src}) --[{rel}]--> ({tgt})")

    # 3. 模拟：LLM 提问检索
    # 假设用户问：“这把刀有什么线索？”
    # 我们提取关键词 "刀"。GraphEngine 使用 CONTAINS 进行模糊匹配，所以"刀"能匹配"带血的刀"
    print("\n[*] 模拟用户提问: '这把刀有什么线索？'")
    keywords = ["刀"]

    # 1跳检索 (应该能查到：案发现场包含刀，刀上有指纹)
    context_1hop = engine.search_subgraph(keywords, sid, pid, hops=1)
    print_box("1-Hop 检索结果 (直接关联)", context_1hop)

    # 2跳检索 (更有趣，能看到指纹指向的人，以及这个人与受害者的关系)
    print("[*] 模拟用户提问: '根据线索能推理出嫌疑人吗？' (扩大搜索范围)")
    context_2hop = engine.search_subgraph(keywords, sid, pid, hops=2)
    print_box("2-Hop 检索结果 (推理关联)", context_2hop)

    # 4. 模拟：多关键词搜索
    # 假设用户问：“目击者和受害者有什么联系吗？”
    print("[*] 模拟用户提问: '目击者C 和 受害者Bob 有联系吗？'")
    keywords_multi = ["目击者C", "受害者Bob"]
    context_multi = engine.search_subgraph(keywords_multi, sid, pid, hops=2)
    print_box("多关键词路径检索", context_multi)

    # 5. 模拟：数据迁移 (存档)
    print("[*] 模拟系统操作: 将当前案卷存档 (数据迁移)")
    new_sid = "archive_案件_001"
    engine.migrate(
        from_context={"session_id": sid, "persona_id": pid},
        to_context={"session_id": new_sid, "persona_id": pid},
    )

    # 验证旧会话为空
    # 搜索 "侦探"
    old_data = engine.search_subgraph(["侦探"], sid, pid)
    print(f"[*] 检查旧会话数据: {'有残留' if old_data else '已清空 (符合预期)'}")

    # 验证新会话
    new_data = engine.search_subgraph(["侦探"], new_sid, pid,4)
    if "案发现场" in new_data:
        print("[*] 检查新存档数据: 迁移成功！")
        print_box("存档内容预览", new_data)
    else:
        print("[!] 迁移失败")

    # 清理
    engine.close()
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("[*] 演示结束，资源已清理。")


if __name__ == "__main__":
    demo_scenario()
