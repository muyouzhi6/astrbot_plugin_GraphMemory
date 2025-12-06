# data/plugins/astrbot_plugin_GraphMemory/core/graph_engine.py

"""
该模块定义了 `GraphEngine` 类，它是与 Kuzu 图数据库交互的核心。
它封装了所有数据库操作，包括模式初始化、数据写入、复杂查询和维护任务。
"""

import asyncio
import functools
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import kuzu

from astrbot.api import logger

from .graph_entities import (
    EntityNode,
    MentionsRel,
    MessageNode,
    RelatedToRel,
    SessionNode,
    UserNode,
)
from .queries import (
    ADD_ENTITY,
    ADD_MENTION,
    ADD_MESSAGE,
    ADD_RELATION,
    ADD_SESSION,
    ADD_USER,
    ARCHIVE_MESSAGES,
    COUNT_ALL_NODES,
    CREATE_MEMORY_FRAGMENT,
    DELETE_EDGE,
    DELETE_MESSAGES_BY_ID,
    DELETE_NODE_BY_ID,
    FIND_PRUNABLE_MESSAGES,
    FIND_SESSIONS_FOR_CONSOLIDATION,
    GET_ALL_CONTEXTS,
    GET_FULL_GRAPH_BASE,
    GET_FULL_GRAPH_RELATIONS,
    GET_MESSAGES_FOR_CONSOLIDATION,
    KEYWORD_SEARCH_ENTITY,
    LINK_FRAGMENT_TO_SESSION,
    LINK_FRAGMENT_TO_USERS,
    MIGRATE_FIND_MEMORIES,
    MIGRATE_LINK_MEMORIES,
    TRAVERSE_GRAPH,
    VECTOR_SEARCH_ENTITY,
    VECTOR_SEARCH_FRAGMENT,
    VECTOR_SEARCH_MESSAGE,
)
from .schema import get_embedding_dim_from_provider, initialize_schema

# 检查可选的 `jieba` 库是否存在，用于中文分词和关键词提取
try:
    import jieba.analyse

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class GraphEngine:
    """
    图数据库引擎，负责管理所有与 Kuzu DB 的交互。

    主要职责:
    - 初始化数据库连接和图模式 (Schema)。
    - 提供异步接口用于添加、更新和删除图中的节点与关系。
    - 实现复杂的多阶段搜索逻辑，用于从图中检索相关记忆。
    - 执行后台维护任务，如剪枝和记忆巩固。

    线程模型:
    为了确保数据库操作的线程安全，所有数据库的读写操作都在一个
    最大工作线程为1的 `ThreadPoolExecutor` 中执行。这有效地将所有
    数据库访问序列化，防止了并发写入可能导致的数据损坏。
    """

    def __init__(self, db_path: Path, embedding_provider: Any | None):
        """
        初始化 GraphEngine。

        Args:
            db_path (Path): 存放数据库文件的目录路径。
            embedding_provider (Any | None): 用于生成向量的 Embedding Provider 实例，可以为 None。
        """
        self.db_version = 2
        self.db_path = (db_path / f"kuzu_db_v{self.db_version}").resolve().as_posix()
        self.kuzu_db = kuzu.Database(self.db_path)
        self.conn: Any = kuzu.Connection(self.kuzu_db)
        self.embedding_provider = embedding_provider

        embedding_dim = get_embedding_dim_from_provider(embedding_provider)

        # 使用锁和单线程执行器来序列化所有数据库访问，确保线程安全
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="GraphEngine"
        )

        logger.info(f"正在初始化 KuzuDB schema v{self.db_version} at {self.db_path}")
        initialize_schema(self.conn, embedding_dim)

    def set_embedding_provider(self, embedding_provider: Any):
        """延迟设置 embedding provider 并重新检查 schema。"""
        self.embedding_provider = embedding_provider
        embedding_dim = get_embedding_dim_from_provider(embedding_provider)

        # 重新初始化 schema 以确保维度正确
        logger.info(f"检测到 Embedding Provider 更新，重新检查 Schema (维度: {embedding_dim})...")
        initialize_schema(self.conn, embedding_dim)

    def execute_query(self, query: str, params: dict | None = None) -> Any:
        """
        在锁的保护下同步执行一个 Cypher 查询。

        Args:
            query (str): 要执行的 Cypher 查询语句。
            params (dict | None): 查询参数。

        Returns:
            Any: Kuzu 的查询结果对象。
        """
        with self._lock:
            return self.conn.execute(query, params or {})

    def close(self):
        """关闭数据库连接并释放资源。"""
        self._executor.shutdown(wait=True)
        self.kuzu_db = None
        logger.info("[GraphMemory] KuzuDB 资源已释放。")

    async def _run_in_executor(self, func, *args, **kwargs):
        """
        一个异步帮助函数，用于在专用的线程池中运行同步的、阻塞的数据库操作，
        从而避免阻塞主 asyncio 事件循环。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, functools.partial(func, *args, **kwargs)
        )

    # ================= 增 / 改 (Write) =================

    async def add_user(self, user: UserNode):
        """异步添加一个用户节点。"""
        params = {"id": user.id, "name": user.name, "platform": user.platform}
        await self._run_in_executor(self.execute_query, ADD_USER, params)

    async def add_session(self, session: SessionNode):
        """异步添加一个会话节点。"""
        params = {"id": session.id, "type": session.type, "name": session.name}
        await self._run_in_executor(self.execute_query, ADD_SESSION, params)

    async def add_entity(self, entity: EntityNode):
        """异步添加一个实体节点，如果需要，会先生成 embedding。"""
        if entity.embedding is None and self.embedding_provider:
            entity.embedding = await self.embedding_provider.embed(entity.name)
        params = {
            "name": entity.name,
            "type": entity.type,
            "summary": entity.summary,
            "embedding": entity.embedding,
        }
        await self._run_in_executor(self.execute_query, ADD_ENTITY, params)

    async def add_message(self, message: MessageNode):
        """异步添加一个消息节点，并将其连接到用户和会话。如果需要，会先生成 embedding。"""
        if message.embedding is None and self.embedding_provider:
            message.embedding = await self.embedding_provider.embed(message.content)
        params = {
            "user_id": message.sender_id,
            "session_id": message.session_id,
            "msg_id": message.id,
            "content": message.content,
            "timestamp": message.timestamp,
            "embedding": message.embedding,
        }
        await self._run_in_executor(self.execute_query, ADD_MESSAGE, params)

    async def add_relation(self, rel: RelatedToRel):
        """异步添加一个实体间的 `RELATED_TO` 关系。"""
        params = {
            "src_name": rel.src_entity,
            "tgt_name": rel.tgt_entity,
            "relation": rel.relation,
        }
        await self._run_in_executor(self.execute_query, ADD_RELATION, params)

    async def add_mention(self, mention: MentionsRel):
        """异步添加一个从消息到实体的 `MENTIONS` 关系。"""
        params = {
            "msg_id": mention.message_id,
            "entity_name": mention.entity_name,
            "sentiment": mention.sentiment,
        }
        await self._run_in_executor(self.execute_query, ADD_MENTION, params)

    # ================= 查 / 召回 (Read) =================

    async def search(
        self,
        query: str,
        query_embedding: list[float],
        session_id: str,
        vector_top_k: int,
        keyword_top_k: int,
        max_items: int,
    ) -> str:
        """
        执行多阶段的记忆搜索，并返回格式化为文本的上下文。

        Args:
            query (str): (重写后的) 用户查询。
            query_embedding (list[float]): 查询的向量表示。
            session_id (str): 当前会话 ID。
            vector_top_k (int): 向量搜索的 top_k。
            keyword_top_k (int): 关键词搜索的 top_k。
            max_items (int): 最终返回的最大上下文项目数。

        Returns:
            str: 格式化后的上下文文本，用于注入到 LLM 的 prompt 中。
        """
        return await self._run_in_executor(
            self._search_sync,
            query,
            query_embedding,
            session_id,
            vector_top_k,
            keyword_top_k,
            max_items,
        )

    def _search_sync(
        self,
        query: str,
        query_embedding: list[float],
        session_id: str,
        vector_top_k: int,
        keyword_top_k: int,
        max_items: int,
    ) -> str:
        """搜索逻辑的同步实现。"""
        # --- 阶段 1: 混合召回 (Hybrid Retrieval) ---
        recalled_items = []

        # 1.1 向量召回：在实体、消息和记忆摘要上进行相似度搜索
        entity_res = self._vector_search(
            "Entity", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [{"type": "Entity", "score": r["score"], **r["node"]} for r in entity_res]
        )

        msg_res = self._vector_search(
            "Message", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [{"type": "Message", "score": r["score"], **r["node"]} for r in msg_res]
        )

        frag_res = self._vector_search(
            "MemoryFragment", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [
                {"type": "MemoryFragment", "score": r["score"], **r["node"]}
                for r in frag_res
            ]
        )

        # 1.2 关键词召回：提取查询中的关键词，在实体上进行文本搜索
        keywords = self._extract_keywords_local(query)
        kw_entity_res = self._keyword_search(keywords, session_id, limit=keyword_top_k)
        # 添加关键词召回的实体，同时去重
        existing_entity_names = {
            item["name"] for item in recalled_items if item["type"] == "Entity"
        }
        for r in kw_entity_res:
            if r["node"]["name"] not in existing_entity_names:
                recalled_items.append(
                    {"type": "Entity", "score": r["score"], **r["node"]}
                )

        if not recalled_items:
            return ""

        # --- 阶段 2: 图扩展 (Graph Expansion) ---
        # 将召回的节点作为种子，在图上进行遍历，获取其一跳邻居和关系
        seed_ids = {item.get("id") or item.get("name") for item in recalled_items}
        traversal_context = self._traverse_graph(list(seed_ids))

        # --- 阶段 3: 重排序与格式化 (Rerank & Format) ---
        # 对所有召回和扩展的项进行加权排序，并格式化为最终的文本上下文
        return self._rerank_and_format_context(
            recalled_items, traversal_context, max_items
        )

    def _vector_search(
        self, table_name: str, vector: list[float], session_id: str, top_k: int = 3
    ) -> list[dict]:
        """
        在指定的表上执行向量搜索。

        Returns:
            list[dict]: 包含节点数据和相似度得分的字典列表。
        """
        params = {"vector": vector, "sid": session_id, "top_k": top_k}

        # 根据表名选择合适的查询语句
        if table_name == "Entity":
            query = VECTOR_SEARCH_ENTITY.format(table_name=table_name, top_k_multiplied=top_k * 5)
        elif table_name == "Message":
            query = VECTOR_SEARCH_MESSAGE.format(table_name=table_name, top_k_multiplied=top_k * 5)
        elif table_name == "MemoryFragment":
            query = VECTOR_SEARCH_FRAGMENT.format(table_name=table_name, top_k_multiplied=top_k * 5)
        else:
            return []

        results = []
        try:
            res = self.execute_query(query, params)
            while res.has_next():
                node_data, score = res.get_next()
                results.append({"node": node_data, "score": score})
        except Exception as e:
            logger.error(f"[GraphMemory] 在 '{table_name}' 上进行向量搜索失败: {e}")
        return results

    def _extract_keywords_local(self, query: str) -> list[str]:
        """使用 jieba (如果可用) 或简单的空格分割来提取关键词。"""
        if JIEBA_AVAILABLE:
            keywords = jieba.analyse.extract_tags(query, topK=3, withWeight=False)
            return [str(k) for k in keywords]
        else:
            # 如果没有 jieba，使用简单的分词作为后备
            return [w for w in query.split() if len(w) > 2][:3]

    def _keyword_search(
        self, keywords: list[str], session_id: str, limit: int = 3
    ) -> list[dict]:
        """在实体名称上执行关键词搜索。"""
        if not keywords:
            return []

        params = {"keywords": keywords, "limit": limit}
        results = []
        try:
            res = self.execute_query(KEYWORD_SEARCH_ENTITY, params)
            while res.has_next():
                node_data, score = res.get_next()
                results.append({"node": node_data, "score": score})
        except Exception as e:
            logger.error(f"[GraphMemory] 关键词搜索失败: {e}")
        return results

    def _traverse_graph(self, seed_ids: list[str], hops: int = 1) -> dict[str, list]:
        """
        从一组种子节点出发，在图上遍历指定跳数，返回邻近的节点和关系。
        """
        context = {"nodes": [], "edges": []}
        if not seed_ids:
            return context

        params = {"seed_ids": seed_ids}

        try:
            res = self.execute_query(TRAVERSE_GRAPH, params)
            while res.has_next():
                n, r, m = res.get_next()
                context["nodes"].append(n)
                context["nodes"].append(m)
                # 将 Kuzu 的关系字典格式化为边信息
                edge_info = {
                    "from": n.get("id") or n.get("name"),
                    "to": m.get("id") or m.get("name"),
                    "label": r["_label"],
                    "properties": {k: v for k, v in r.items() if not k.startswith("_")},
                }
                context["edges"].append(edge_info)
        except Exception as e:
            logger.error(f"[GraphMemory] 图遍历失败: {e}")

        return context

    def _rerank_and_format_context(
        self, recalled_items: list[dict], traversal_context: dict, max_items: int
    ) -> str:
        """
        对所有召回和扩展的上下文信息进行重排序，并格式化为最终的文本输出。
        排序逻辑考虑了初始得分、节点类型权重和时间衰减。
        """
        import time
        from datetime import datetime

        context_items = []
        processed_ids = set()

        # 1. 处理召回的项，计算初始得分
        for item in recalled_items:
            item_id = item.get("id") or item.get("name")
            if item_id in processed_ids:
                continue

            score = item.get("score", 0.0)

            # 应用类型权重：摘要 > 实体 > 消息
            type_weights = {"MemoryFragment": 1.5, "Entity": 1.2, "Message": 1.0}
            score *= type_weights.get(item["type"], 1.0)

            # 对有时间戳的节点（如消息）应用时间衰减
            timestamp = item.get("timestamp")
            if timestamp:
                age_days = (time.time() - timestamp) / (3600 * 24)
                decay_factor = 1 / (1 + age_days * 0.1)  # 简单的衰减函数
                score *= decay_factor

            context_items.append({"id": item_id, "data": item, "score": score})
            processed_ids.add(item_id)

        # 2. 处理图遍历扩展出的项，给予一个较低的基础分
        traversed_nodes = {
            (n.get("id") or n.get("name")): n for n in traversal_context["nodes"]
        }
        for node_id, node_data in traversed_nodes.items():
            if node_id in processed_ids:
                continue
            context_items.append(
                {"id": node_id, "data": node_data, "score": 0.5}
            )
            processed_ids.add(node_id)

        # 3. 按最终得分对所有项进行降序排序
        context_items.sort(key=lambda x: x["score"], reverse=True)

        # 4. 将得分最高的 K 项格式化为文本
        formatted_lines = []
        final_items_to_show = max_items

        # 优先添加记忆摘要
        summaries = [
            item for item in context_items if item["data"]["_label"] == "MemoryFragment"
        ]
        if summaries:
            formatted_lines.append("相关记忆摘要:")
            for s_item in summaries[:2]:  # 最多显示2条摘要
                ts = datetime.fromtimestamp(s_item["data"]["timestamp"]).strftime(
                    "%Y-%m-%d"
                )
                formatted_lines.append(f"- [日期: {ts}]: {s_item['data']['text']}")
                final_items_to_show -= 1

        # 添加相关实体
        entities = [
            item for item in context_items if item["data"]["_label"] == "Entity"
        ]
        if entities:
            formatted_lines.append("\n相关概念:")
            for e_item in entities[:3]:  # 最多显示3个实体
                formatted_lines.append(f"- 概念: {e_item['data']['name']}")
                final_items_to_show -= 1

        # 添加图关系（事实）
        if traversal_context["edges"]:
            formatted_lines.append("\n相关事实:")
            for edge in traversal_context["edges"][:3]:  # 最多显示3条关系
                formatted_lines.append(
                    f"- 事实: ({edge['from']})-[{edge['label']}]->({edge['to']})"
                )
                final_items_to_show -= 1

        # 如果还有空间，添加相关的历史消息
        messages = [
            item for item in context_items if item["data"]["_label"] == "Message"
        ]
        if messages and final_items_to_show > 0:
            formatted_lines.append("\n相关历史消息:")
            for m_item in messages[:final_items_to_show]:
                ts = datetime.fromtimestamp(m_item["data"]["timestamp"]).strftime(
                    "%Y-%m-%d"
                )
                formatted_lines.append(
                    f"- [日期: {ts}]: ...{m_item['data']['content'][:80]}..."
                )

        return "\n".join(formatted_lines)

    async def search_for_visualization(
        self,
        query: str,
        query_embedding: list[float],
        session_id: str,
        vector_top_k: int,
        keyword_top_k: int,
    ) -> dict:
        """[异步] 执行搜索并返回用于可视化的原始图组件。"""
        return await self._run_in_executor(
            self._search_for_visualization_sync,
            query,
            query_embedding,
            session_id,
            vector_top_k,
            keyword_top_k,
        )

    def _search_for_visualization_sync(
        self,
        query: str,
        query_embedding: list[float],
        session_id: str,
        vector_top_k: int,
        keyword_top_k: int,
    ) -> dict:
        """[同步] 执行搜索并返回一个包含 'nodes' 和 'edges' 的字典。"""
        # 1. 混合召回
        recalled_items = []
        entity_res = self._vector_search(
            "Entity", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [{"type": "Entity", "score": r["score"], **r["node"]} for r in entity_res]
        )
        msg_res = self._vector_search(
            "Message", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [{"type": "Message", "score": r["score"], **r["node"]} for r in msg_res]
        )
        frag_res = self._vector_search(
            "MemoryFragment", query_embedding, session_id, top_k=vector_top_k
        )
        recalled_items.extend(
            [
                {"type": "MemoryFragment", "score": r["score"], **r["node"]}
                for r in frag_res
            ]
        )

        keywords = self._extract_keywords_local(query)
        kw_entity_res = self._keyword_search(keywords, session_id, limit=keyword_top_k)
        existing_entity_names = {
            item["name"] for item in recalled_items if item["type"] == "Entity"
        }
        for r in kw_entity_res:
            if r["node"]["name"] not in existing_entity_names:
                recalled_items.append(
                    {"type": "Entity", "score": r["score"], **r["node"]}
                )

        if not recalled_items:
            return {"nodes": [], "edges": []}

        # 2. 图遍历扩展
        seed_ids = {item.get("id") or item.get("name") for item in recalled_items}
        traversal_context = self._traverse_graph(list(seed_ids))

        # 3. 合并并格式化所有相关节点
        all_nodes = {
            (n.get("id") or n.get("name")): n for n in traversal_context["nodes"]
        }
        for item in recalled_items:
            node_id = item.get("id") or item.get("name")
            if node_id not in all_nodes:
                node_data = item.copy()
                if "_label" not in node_data:
                    node_data["_label"] = node_data.get("type", "Unknown")
                all_nodes[node_id] = node_data

        # 4. 格式化为 vis.js 兼容的格式
        vis_nodes = []
        nodes_seen = set()
        for node_id, node_data in all_nodes.items():
            if node_id not in nodes_seen:
                vis_node = {
                    "id": node_id,
                    "label": node_data.get("name") or node_data.get("content", "")[:30],
                    "group": node_data["_label"],
                    "title": "\n".join(f"{k}: {v}" for k, v in node_data.items()),
                }
                vis_nodes.append(vis_node)
                nodes_seen.add(node_id)

        return {"nodes": vis_nodes, "edges": traversal_context["edges"]}

    # ================= 维护 (Maintenance) =================
    async def prune_graph(self, max_nodes: int) -> int:
        """
        [异步] 剪枝图谱，移除最旧的 Message 节点以将节点总数保持在限制内。
        """
        return await self._run_in_executor(self._prune_graph_sync, max_nodes)

    def _prune_graph_sync(self, max_nodes: int) -> int:
        """[同步] 剪枝图谱的实现。"""
        try:
            # 1. 获取当前节点总数
            res = self.execute_query(COUNT_ALL_NODES)
            current_nodes = res.get_next()[0] if res.has_next() else 0

            if current_nodes <= max_nodes:
                logger.debug(
                    f"[GraphMemory] 节点数 ({current_nodes}) 在限制 ({max_nodes}) 内，无需剪枝。"
                )
                return 0

            nodes_to_delete = current_nodes - max_nodes
            logger.info(
                f"[GraphMemory] 需要剪枝。当前: {current_nodes}, 限制: {max_nodes}。目标删除: {nodes_to_delete} 个节点。"
            )

            # 2. 查找要删除的最旧的 Message 节点 ID
            res = self.execute_query(FIND_PRUNABLE_MESSAGES, {"limit": nodes_to_delete})
            ids_to_delete = [row[0] for row in res.get_all()]

            if not ids_to_delete:
                logger.info("[GraphMemory] 未找到可剪枝的消息。")
                return 0

            # 3. 分批执行删除操作以避免单个事务过大
            deleted_count = 0
            batch_size = 100
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i : i + batch_size]
                self.execute_query(DELETE_MESSAGES_BY_ID, {"ids": batch})
                deleted_count += len(batch)

            logger.info(
                f"[GraphMemory] 剪枝完成。精确删除了 {deleted_count} 个消息节点。"
            )
            return deleted_count
        except Exception as e:
            logger.error(
                f"[GraphMemory] 图剪枝过程中发生错误: {e}", exc_info=True
            )
            return 0

    async def flush_access_stats(self):
        """(占位) 刷新访问统计信息，当前版本未实现。"""
        logger.warning(
            "flush_access_stats 函数在新版 GraphEngine 中尚未实现。"
        )
        pass

    async def find_sessions_for_consolidation(self, threshold: int) -> list[str]:
        """
        [异步] 查找有足够多未归档消息、需要进行记忆巩固的会话。
        """
        return await self._run_in_executor(
            self._find_sessions_for_consolidation_sync, threshold
        )

    def _find_sessions_for_consolidation_sync(self, threshold: int) -> list[str]:
        """[同步] 查找需要巩固的会话的实现。"""
        try:
            res = self.execute_query(FIND_SESSIONS_FOR_CONSOLIDATION, {"threshold": threshold})
            return [row[0] for row in res.get_all()] if res.has_next() else []
        except Exception as e:
            logger.error(
                f"[GraphMemory] 查找需要巩固的会话失败: {e}"
            )
            return []

    def get_messages_for_consolidation(
        self, session_id: str, limit: int = 50
    ) -> tuple[list[str], str, list[str]] | None:
        """
        获取一个会话中用于巩固的一批最旧的消息。

        Returns:
            一个元组 (消息ID列表, 拼接好的对话文本, 参与者ID列表)，如果无消息则返回 None。
        """
        params = {"sid": session_id, "limit": limit}

        try:
            res = self.execute_query(GET_MESSAGES_FOR_CONSOLIDATION, params)
            if not res.has_next():
                return None

            message_ids = []
            user_ids = set()
            log_lines = []
            while res.has_next():
                mid, uid, user_name, content = res.get_next()
                message_ids.append(mid)
                user_ids.add(uid)
                log_lines.append(f"[{user_name}]: {content}")

            return message_ids, "\n".join(log_lines), list(user_ids)
        except Exception as e:
            logger.error(f"[GraphMemory] 获取用于巩固的消息失败: {e}")
            return None

    async def consolidate_memory(
        self,
        session_id: str,
        summary_text: str,
        message_ids: list[str],
        user_ids: list[str],
    ):
        """
        [异步] 执行记忆巩固：创建摘要节点，并归档旧消息。
        """
        if not self.embedding_provider:
            logger.warning(
                "[GraphMemory] 未配置 embedding provider，无法创建记忆片段。"
            )
            return

        try:
            summary_embedding = await self.embedding_provider.embed(summary_text)
            await self._run_in_executor(
                self._consolidate_memory_sync,
                session_id,
                summary_text,
                message_ids,
                user_ids,
                summary_embedding,
            )
        except Exception as e:
            logger.error(
                f"为摘要生成 embedding 或执行巩固时失败: {e}",
                exc_info=True,
            )

    def _consolidate_memory_sync(
        self,
        session_id: str,
        summary_text: str,
        message_ids: list[str],
        user_ids: list[str],
        summary_embedding: list[float],
    ):
        """[同步] 记忆巩固的实现。"""
        import time
        import uuid

        # 1. 创建一个新的 MemoryFragment 节点来存储摘要
        fragment_id = str(uuid.uuid4())
        ts = int(time.time())

        self.execute_query(
            CREATE_MEMORY_FRAGMENT,
            {
                "id": fragment_id,
                "text": summary_text,
                "ts": ts,
                "embedding": summary_embedding,
            },
        )

        # 2. 将新的摘要节点连接到对应的会话
        self.execute_query(LINK_FRAGMENT_TO_SESSION, {"sid": session_id, "fid": fragment_id})

        # 2.5 将摘要节点连接到相关的用户
        if user_ids:
            self.execute_query(LINK_FRAGMENT_TO_USERS, {"fid": fragment_id, "uids": user_ids})

        # 3. 将被摘要的原始消息标记为已归档
        batch_size = 100
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i : i + batch_size]
            self.execute_query(ARCHIVE_MESSAGES, {"ids": batch})

        logger.info(
            f"[GraphMemory] 已将 {len(message_ids)} 条消息巩固为会话 {session_id} 的一个记忆片段，并关联了 {len(user_ids)} 个用户。"
        )

    async def get_graph_statistics(self) -> dict[str, int] | None:
        """[异步] 获取图谱中各类节点的数量统计。"""
        return await self._run_in_executor(self._get_graph_statistics_sync)

    def _get_graph_statistics_sync(self) -> dict[str, int] | None:
        """[同步] 获取图谱统计的实现。"""
        stats = {}
        node_types = ["User", "Session", "Message", "Entity", "MemoryFragment"]
        try:
            for node_type in node_types:
                res = self.execute_query(f"MATCH (n:{node_type}) RETURN count(n)")
                stats[f"{node_type}_count"] = res.get_next()[0] if res.has_next() else 0
            return stats
        except Exception as e:
            logger.error(f"[GraphMemory] 获取图谱统计失败: {e}")
            return None

    async def migrate_memories(
        self, source_session_id: str, target_session_id: str
    ) -> int:
        """
        [异步] 将一个会话的记忆（摘要）迁移（即关联）到另一个会话。
        """
        return await self._run_in_executor(
            self._migrate_memories_sync, source_session_id, target_session_id
        )

    def _migrate_memories_sync(
        self, source_session_id: str, target_session_id: str
    ) -> int:
        """[同步] 记忆迁移的实现。"""
        # 1. 确保目标会话节点存在
        self.execute_query("MERGE (s:Session {id: $sid})", {"sid": target_session_id})

        # 2. 查找源会话的所有 MemoryFragment 节点
        res = self.execute_query(MIGRATE_FIND_MEMORIES, {"sid": source_session_id})
        if not res.has_next():
            return 0

        memory_fragment_ids = [row[0] for row in res.get_all()]

        # 3. 将这些摘要节点也关联到目标会话
        if not memory_fragment_ids:
            return 0

        self.execute_query(
            MIGRATE_LINK_MEMORIES, {"sid": target_session_id, "mf_ids": memory_fragment_ids}
        )

        logger.info(
            f"已将 {len(memory_fragment_ids)} 条记忆从 {source_session_id} 迁移到 {target_session_id}。"
        )
        return len(memory_fragment_ids)

    async def get_all_contexts(self) -> list[str]:
        """[异步] 获取数据库中所有会话的 ID 列表。"""
        return await self._run_in_executor(self._get_all_contexts_sync)

    def _get_all_contexts_sync(self) -> list[str]:
        """[同步] 获取所有会话 ID 的实现。"""
        try:
            res = self.execute_query(GET_ALL_CONTEXTS)
            return [row[0] for row in res.get_all()] if res.has_next() else []
        except Exception as e:
            logger.error(f"[GraphMemory] 获取所有上下文失败: {e}")
            return []

    async def get_full_graph(self, session_id: str) -> dict | None:
        """[异步] 导出指定会话的完整子图，用于 WebUI 可视化。"""
        return await self._run_in_executor(self._get_full_graph_sync, session_id)

    def _get_full_graph_sync(self, session_id: str) -> dict | None:
        """[同步] 导出完整子图的实现。"""
        graph = {"nodes": [], "edges": []}
        nodes_seen = set()

        def add_node(node_data):
            """辅助函数，用于向图中添加节点并避免重复，同时格式化为 vis.js 兼容格式。"""
            node_id = node_data.get("id") or node_data.get("name")
            if node_id and node_id not in nodes_seen:
                vis_node = {
                    "id": node_id,
                    "label": node_data.get("name") or node_data.get("content", "")[:30],
                    "group": node_data["_label"],  # _label 字段包含节点类型
                    "title": "\n".join(f"{k}: {v}" for k, v in node_data.items()),
                }
                graph["nodes"].append(vis_node)
                nodes_seen.add(node_id)

        try:
            # 1. 获取会话中的所有消息、发送者、实体和摘要等基本节点和关系
            res = self.execute_query(GET_FULL_GRAPH_BASE, {"sid": session_id})

            while res.has_next():
                s, u, m, r_mentions, e, r_has_mem, mf = res.get_next()

                if s:
                    add_node(s)
                if u:
                    add_node(u)
                if m:
                    add_node(m)
                if e:
                    add_node(e)
                if mf:
                    add_node(mf)

                if u and m:
                    graph["edges"].append({"from": u["id"], "to": m["id"], "label": "SENT"})
                if m and s:
                    graph["edges"].append({"from": m["id"], "to": s["id"], "label": "POSTED_IN"})
                if m and e and r_mentions:
                    graph["edges"].append({"from": m["id"], "to": e["name"], "label": "MENTIONS"})
                if s and mf and r_has_mem:
                    graph["edges"].append({"from": s["id"], "to": mf["id"], "label": "HAS_MEMORY"})

            # 2. 单独获取实体间的 `RELATED_TO` 关系
            res_rels = self.execute_query(GET_FULL_GRAPH_RELATIONS, {"sid": session_id})
            while res_rels.has_next():
                e1, r, e2 = res_rels.get_next()
                add_node(e1)
                add_node(e2)
                graph["edges"].append(
                    {"from": e1["name"], "to": e2["name"], "label": r["relation"]}
                )

            return graph
        except Exception as e:
            logger.error(
                f"[GraphMemory] 为会话 '{session_id}' 导出图失败: {e}",
                exc_info=True,
            )
            return None

    async def delete_node_by_id(self, node_id: str, node_type: str) -> bool:
        """[异步] 根据 ID 和类型删除一个节点及其关联的边。"""
        return await self._run_in_executor(
            self._delete_node_by_id_sync, node_id, node_type
        )

    def _delete_node_by_id_sync(self, node_id: str, node_type: str) -> bool:
        """[同步] 删除节点的实现。"""
        # 根据节点类型确定主键字段名
        id_field = "name" if node_type == "Entity" else "id"
        try:
            query = DELETE_NODE_BY_ID.format(node_type=node_type, id_field=id_field)
            self.execute_query(query, {"node_id": node_id})
            logger.info(
                f"[GraphMemory] 已删除类型为 '{node_type}' 的节点 '{node_id}'。"
            )
            return True
        except Exception as e:
            logger.error(f"[GraphMemory] 删除节点 '{node_id}' 失败: {e}")
            return False

    async def delete_edge(
        self, from_id: str, to_id: str, rel_type: str, from_type: str, to_type: str
    ) -> bool:
        """[异步] 删除一条边。"""
        return await self._run_in_executor(
            self._delete_edge_sync, from_id, to_id, rel_type, from_type, to_type
        )

    def _delete_edge_sync(
        self, from_id: str, to_id: str, rel_type: str, from_type: str, to_type: str
    ) -> bool:
        """[同步] 删除边的实现。"""
        from_id_field = "name" if from_type == "Entity" else "id"
        to_id_field = "name" if to_type == "Entity" else "id"
        try:
            query = DELETE_EDGE.format(
                from_type=from_type,
                from_id_field=from_id_field,
                rel_type=rel_type,
                to_type=to_type,
                to_id_field=to_id_field
            )
            self.execute_query(query, {"from_id": from_id, "to_id": to_id})
            logger.info(
                f"[GraphMemory] 已删除从 '{from_id}' 到 '{to_id}' 的 `[{rel_type}]` 边。"
            )
            return True
        except Exception as e:
            logger.error(f"[GraphMemory] 删除边失败: {e}")
            return False

    async def migrate_from_v1(self) -> bool:
        """[异步] (占位) 从 v1 数据库迁移数据。"""
        logger.warning("migrate_from_v1 尚未实现。")
        return True

    async def update_node_properties(self, node_id: str, node_type: str, properties: dict) -> bool:
        """[异步] 更新节点的属性。"""
        return await self._run_in_executor(
            self._update_node_properties_sync, node_id, node_type, properties
        )

    def _update_node_properties_sync(self, node_id: str, node_type: str, properties: dict) -> bool:
        """[同步] 更新节点属性的实现。"""
        id_field = "name" if node_type == "Entity" else "id"

        # 基本的安全措施：目前只允许更新特定的字段
        allowed_updates = {
            "Entity": ["summary", "type"],
            "MemoryFragment": ["text"],
        }

        if node_type not in allowed_updates:
            logger.warning(f"不允许更新节点类型 '{node_type}' 的属性。")
            return False

        set_clauses = []
        params = {"node_id": node_id}

        for key, value in properties.items():
            if key in allowed_updates[node_type]:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = value

        if not set_clauses:
            logger.warning(f"没有为节点 '{node_id}' 提供有效的待更新属性。")
            return False

        query = f"""
            MATCH (n:{node_type} {{{id_field}: $node_id}})
            SET {', '.join(set_clauses)}
        """

        try:
            self.execute_query(query, params)
            logger.info(f"已更新节点 '{node_id}' 的属性: {list(properties.keys())}")
            return True
        except Exception as e:
            logger.error(f"更新节点 '{node_id}' 失败: {e}")
            return False
