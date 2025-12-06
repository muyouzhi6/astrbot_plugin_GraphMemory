<div align="center">

# astrbot_plugin_GraphMemory

<p>
    <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version">
    <img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg" alt="License">
    <img src="https://img.shields.io/badge/status-beta-orange" alt="Status">
</p>

<h3> 基于 kuzu 的图数据库记忆插件 </h3>

> **注意**：当前为测试版本，功能可能不稳定。

</div>

## 简介

一个简单的图数据库记忆插件，基于 kuzu 实现。它能够自动从对话中提取实体和关系，构建知识图谱，并在后续的对话中检索相关信息，赋予 Bot 更连贯的上下文理解能力。

## 核心特性

*   **自动旁听学习**: 能够分析群聊和私聊中的对话，自动提取关键信息存入图数据库。
*   **智能记忆检索**: 在 Bot 回复前，根据用户消息的关键词自动检索相关记忆，并注入到 Prompt 中。
*   **人格隔离**: 支持不同人格拥有独立的记忆空间，互不干扰；也支持配置特定会话共享记忆。
*   **自动修剪**: 设置最大节点数限制，定期清理陈旧或不重要的记忆，保持数据库高效。

## 配置详解

配置文件位于插件目录下的 `_conf_schema.json` (或通过 AstrBot 管理面板配置)。

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `enable_group_learning` | bool | `true` | 是否开启群聊旁听学习。开启后，Bot 将会分析群聊中非直接对话并提取记忆。 |
| `learning_model_id` | string | `""` | 用于记忆提取的专用 LLM 模型 ID。建议使用价格较低且指令遵循能力强的模型。留空则复用当前会话的模型。 |
| `confidence_threshold` | float | `0.6` | 记忆采纳的置信度阈值 (0.0 - 1.0)。低于此置信度的关系将被丢弃。 |
| `enable_persona_isolation` | bool | `true` | 是否默认开启人格记忆隔离。 |
| `persona_isolation_exceptions` | list | `[]` | 人格隔离例外列表。填写 `unified_msg_origin`。 |
| `keyword_extraction_mode` | string | `"local"` | 记忆检索的关键词提取模式。`local` (使用 jieba，速度快且免费) 或 `llm` (使用 LLM，更智能但有成本)。 |
| `keyword_extraction_provider` | string | `""` | 如果关键词提取模式为 llm，指定使用的模型 ID。留空则复用 `learning_model_id` 或当前会话模型。 |
| `max_global_nodes` | int | `5000` | 全局最大节点数限制。当节点总数超过此值时，会触发清理机制。 |
| `prune_interval` | int | `3600` | 记忆清理检查间隔（秒）。 |

## 指令说明

```bash
migrate_memory <target_session>
```
将当前会话的记忆迁移到目标会话。

## 未来开发计划

- [ ] 优化消息缓冲区处理策略，提高提取效率。
- [ ] 添加 WebUI 功能，支持可视化查看和管理知识图谱。
- [ ] 注册更多插件指令，方便手动管理记忆。



AstrBot 无限对话记忆架构蓝图：基于 GraphRAG 与增量摘要的混合记忆系统深度研究报告1. 执行摘要在当前大语言模型（LLM）驱动的对话系统领域，实现“无限对话”并保留长期记忆是通向通用人工智能（AGI）代理的关键一步。尽管 LLM 的上下文窗口已扩展至 128k 甚至 1M token，但在实际应用中，单纯依赖长上下文面临着推理成本高昂、响应延迟增加以及“迷失中间（Lost-in-the-Middle）”现象导致的召回率下降等严峻挑战。对于运行在 QQ、Telegram、微信等即时通讯（IM）平台上的 AstrBot 而言，构建一个既能处理私聊又能应对复杂群聊环境的无限记忆插件，需要超越传统的向量检索增强生成（Vector RAG），迈向结构化、关系感知的图检索增强生成（GraphRAG）。本报告提出了一套详尽的技术方案，旨在为 AstrBot 设计并实现一个名为 astrbot_plugin_infinite_memory 的插件。该方案的核心在于构建一个混合记忆架构（Hybrid Memory Architecture），它结合了用于模糊语义检索的向量数据库与用于结构化关系推理的图数据库。为了适应 AstrBot 的轻量级部署特性（通常运行在个人服务器或家用设备上），本方案强烈推荐采用嵌入式属性图数据库 KuzuDB，它无需独立的服务器进程，并原生支持向量索引，从而极大简化了运维复杂度。架构上，系统被设计为异步的双流处理模式：即时响应流保证用户体验的流畅性，而记忆固化流在后台利用小参数模型（如 GPT-4o-mini 或本地 Llama 3）进行实体的抽取、关系的构建以及增量摘要的生成。通过引入时间维度的图谱设计，系统能够处理事实的演变（如用户爱好的变更），并利用多跳推理（Multi-hop Reasoning）解决复杂的群聊上下文依赖问题。本报告将分章节深入探讨从理论基础、技术选型、图谱本体设计、算法实现到 AstrBot 插件具体开发的每一个细节，旨在为开发者提供一份达到工业级标准的实施手册。2. 引言：对话系统中的记忆困境与破局2.1 上下文窗口的幻觉与现实随着 GPT-4 和 Claude 3 等模型的发布，长上下文窗口似乎成为解决记忆问题的“银弹”。然而，在实际的 AstrBot 部署场景中，长上下文存在不可忽视的边际递减效应。首先是经济成本，每次对话都将历史记录全量回传给 API 会导致 token 消耗呈线性甚至指数级增长，这对于个人开发者或小型社区是不可持续的。其次是推理延迟，处理 10 万 token 的上下文往往需要数秒甚至数十秒，这在即时通讯场景中是无法接受的体验。最重要的是注意力分散，研究表明 LLM 在处理超长文本时，对中间位置信息的检索能力显著下降 1。因此，“无限记忆”不能等同于“无限输入”。它必须是一个经过高度压缩、索引和结构化的存储系统，只在必要时提取最相关的信息片段（Relevant Context）。2.2 向量 RAG 的局限性传统的 RAG 方案将聊天记录切片并存储在向量数据库（如 Chroma、Milvus）中。当用户提问时，系统检索语义最相似的片段。这种方法在处理静态文档时表现良好，但在动态对话中却屡屡碰壁：代词消解失败：如果用户说“我喜欢它”，而上一句是关于“Rust 语言”的，向量切片如果切断了这两句话的联系，存储的“我喜欢它”将毫无意义。时间错位：向量数据库缺乏原生的时间感知。对于“我上周的想法”和“我现在的想法”，向量相似度可能无法区分，导致旧信息覆盖新信息，或检索到过时的事实 3。群聊拓扑丢失：在群聊中，多条对话线索并行穿插。单纯的语义检索无法理解回复关系（Reply-to）和引用关系，容易将不同话题的发言混淆 4。2.3 GraphRAG 的范式转移GraphRAG（图检索增强生成）代表了记忆系统的下一次进化。它不再将数据视为孤立的文本块，而是视为由实体（Nodes）和关系（Edges）构成的网络。在 GraphRAG 中，“用户 A 回复了用户 B 关于 Python 的问题”不再是模糊的文本，而是一条明确的路径：(User A)-->(Message)-->(Topic: Python)。这种结构化表示使得系统能够进行多跳推理，例如回答“群里有哪些人讨论过 AI Agent？”这样的聚合性问题，而不仅仅是匹配关键词 5。3. 技术选型与架构全景为了在 AstrBot 生态中实现这一愿景，我们需要精心选择技术栈。AstrBot 基于 Python 开发，具有高度的插件化特性和异步事件总线机制，这决定了我们的记忆系统必须是 Python 原生的、异步友好的且资源占用可控的。3.1 核心数据库：为何选择 KuzuDB？在图数据库领域，Neo4j 长期占据主导地位，但对于 AstrBot 插件而言，Neo4j 显得过于沉重。它依赖 Java 环境，需要运行独立的 Docker 容器或后台进程，并通过网络协议（Bolt）通信。这违背了 AstrBot “一键部署、轻量级”的设计初衷。相比之下，KuzuDB 是一个颠覆性的选择，它是专为 Python 和 C++ 设计的嵌入式属性图数据库。特性维度Neo4j (Community)NetworkX (In-Memory)KuzuDB (Embedded)部署模式独立服务器进程 (Java)Python 内存对象嵌入式库 (C++/Python Binding)存储持久化磁盘持久化需手动序列化 (Pickle/JSON)磁盘列式存储 (Columnar Store)查询语言CypherPython APICypher向量支持需插件或单独 Vector DB无原生支持节点属性向量索引规模上限PB 级受限于 RAMTB 级 (Out-of-Core Processing)适用场景企业级集群算法原型验证单机应用、Agent 记忆KuzuDB 的核心优势在于它运行在进程内（In-Process），没有网络开销，且支持向量索引。这意味着我们不需要引入额外的向量数据库（如 LanceDB 或 FAISS），KuzuDB 可以同时处理结构化查询（“查找所有用户”）和语义查询（“查找描述与此向量相似的节点”），实现了完美的混合检索（Hybrid Retrieval） 7。3.2 辅助组件与 AstrBot 接口AstrBot Event Bus (StarRouter): 插件将注册 on_message 监听器来捕获所有聊天流，并注册 on_llm_request 钩子来在 LLM 请求发送前注入记忆上下文 10。LLM Provider: 利用 AstrBot 统一的 Context.get_llm_provider() 接口。为了降低成本，记忆的抽取（Ingestion）和摘要（Summarization）建议配置使用轻量级模型（如 GPT-4o-mini 或本地 Ollama 模型），而最终的对话回复使用高智力模型（如 Claude 3.5 Sonnet）12。LangChain (Optional): 虽然 LangChain 提供了图构建工具，但为了保持插件的轻量和可控，建议直接封装 KuzuDB 的 Python API，仅在必要时引入 LangChain 的文本分割器（Text Splitter）13。4. 记忆本体论：图谱 Schema 设计图数据库的威力取决于 Schema（本体）的设计。对于无限对话记忆，我们需要一个既能捕捉即时通讯细节，又能承载长期抽象概念的 Schema。我们将采用 KuzuDB 的 DDL（数据定义语言）来定义节点表（Node Tables）和关系表（Rel Tables）。4.1 节点定义 (Nodes)4.1.1 用户节点 (User)代表参与对话的实体。在群聊环境中，用户身份的唯一性至关重要。id (STRING, Primary Key): 格式为 {platform}_{user_id}，例如 qq_12345678。name (STRING): 用户当前的显示名称。platform (STRING): 来源平台（QQ, Telegram, WeChat）。profile_embedding (FLOAT_LIST): 用户画像的向量表示，用于快速匹配具有相似特征的用户。4.1.2 会话节点 (Session)代表对话发生的场所，用于实现多租户隔离。id (STRING, Primary Key): 格式为 {platform}_{group_id} 或 {platform}_private_{user_id}。type (STRING): 枚举值 GROUP 或 PRIVATE。name (STRING): 群名称或私聊对象名称。4.1.3 消息节点 (Message)代表原始的对话记录。为了实现无限记忆，这些节点在一定时间后会被“归档”或“摘要化”，不再直接参与检索，但在图谱中保留作为证据链。id (STRING, Primary Key): 平台唯一消息 ID。content (STRING): 消息原始内容（可能会被截断以节省空间）。timestamp (INT64): Unix 时间戳。embedding (FLOAT_LIST): 消息内容的语义向量。4.1.4 实体节点 (Entity)代表从对话中抽取的知识原子，如“Python”、“上海”、“周末聚会”。name (STRING, Primary Key): 归一化后的实体名称（如将 “JS”, “JavaScript” 统一为 “JavaScript”）。type (STRING): 实体类型（Person, Location, Event, Concept, Product）。summary (STRING): 关于该实体的描述性摘要。embedding (FLOAT_LIST): 实体的语义向量，用于模糊搜索。4.1.5 记忆片段节点 (MemoryFragment)代表经过 LLM 总结后的高级记忆，如“用户 A 在 2024 年表示想去日本旅游”。id (STRING, Primary Key): UUID。text (STRING): 记忆的自然语言描述。valid_from (INT64): 记忆生效时间。valid_until (INT64): 记忆失效时间（用于处理状态变更）。embedding (FLOAT_LIST): 记忆内容的向量。4.2 关系定义 (Relationships)PARTICIPATED_IN: (User)-->(Session) - 记录用户属于哪些群组。SENT: (User)-->(Message) - 记录消息发送者。POSTED_IN: (Message)-->(Session) - 记录消息所属会话，这是实现多租户隔离的关键边 14。REPLIES_TO: (Message)-->(Message) - 显式记录回复关系，重建对话树。MENTIONS: (Message)-->(Entity) - 消息中提到了哪些实体。属性 sentiment (STRING): 情感倾向（Positive, Negative, Neutral）。HAS_MEMORY: (User|Session)-->(MemoryFragment) - 将记忆挂载到特定用户或群组上。RELATED_TO: (Entity)-->(Entity) - 实体间的语义关联（如 Python -> Programming）。4.3 DDL 实现示例 (Python)Python# KuzuDB Schema 初始化代码片段
import kuzu

db = kuzu.Database('./data/astrbot_memory.kuzu')
conn = kuzu.Connection(db)

# 创建用户表
conn.execute("""
    CREATE NODE TABLE User(
        id STRING, 
        name STRING, 
        platform STRING, 
        PRIMARY KEY (id)
    )
""")

# 创建实体表，包含向量索引支持
conn.execute("""
    CREATE NODE TABLE Entity(
        name STRING, 
        type STRING, 
        summary STRING, 
        embedding FLOAT, 
        PRIMARY KEY (name)
    )
""")

# 创建 MENTIONS 关系表
conn.execute("CREATE REL TABLE MENTIONS(FROM Message TO Entity, sentiment STRING)")
5. 核心算法逻辑：从对话流到知识图谱要实现“无限对话”，系统必须具备**增量式（Incremental）**的处理能力。我们不能在每次新消息到来时重构整个图谱。5.1 异步摄入流水线 (Ingestion Pipeline)为了不阻塞 AstrBot 的主线程（影响回复速度），摄入过程必须是异步的 (asyncio)。消息捕获：插件监听 on_message 事件。预过滤：使用正则或轻量级 NLP 过滤掉无意义的短语（如“哈哈”、“收到”），减少 LLM 调用成本。信息抽取 (Information Extraction)：将当前消息及前 2-3 条上下文发送给提取模型（Extractor LLM）。Prompt 设计：“作为知识图谱构建者，请从以下对话中提取实体、关系和事实。忽略闲聊。输出 JSON 格式的三元组。”实体消歧：LLM 需要处理指代消解（Coreference Resolution），将“它”映射到具体的实体对象 15。图谱更新 (Graph Upsert)：使用 Cypher 的 MERGE 语句。如果实体已存在，则更新其属性或增加引用计数；如果不存在，则创建。例如：MERGE (u:User {id: '...'}) MERGE (e:Entity {name: 'AstrBot'}) MERGE (u)-->(e)。5.2 记忆固化与遗忘机制 (Consolidation & Forgetting)无限记忆的关键在于遗忘琐碎细节，保留核心概念。这是一个模仿人类记忆巩固的过程。短期记忆缓冲区 (STM)：最近的 N 条消息（例如 50 条）保留在 AstrBot 的原生上下文中，同时也作为 Message 节点存储在图中。周期性摘要：每当某个 Session 积累了 M 条新消息（例如 100 条），触发一次社区检测（Community Detection）或简单的时间窗摘要。系统查询该时间段内的所有 Message 和涉及的 Entity。LLM 生成一段高层摘要：“在这个时间段内，群友们讨论了 AstrBot 的插件开发，特别是关于图数据库选型的问题。”该摘要被存储为新的 MemoryFragment 节点，并连接到 Session 和相关 User。图谱剪枝 (Pruning)：为了防止图谱无限膨胀，系统可以配置策略，定期归档超过一定时间（如 30 天）且没有被引用的原始 Message 节点，仅保留 MemoryFragment 和 Entity 节点。这实现了从**情景记忆（Episodic）向语义记忆（Semantic）**的转化 17。5.3 冲突解决策略当用户更新信息时（例如“我不喜欢 Python 了，我现在学 Go”），图谱必须反映这一变化。时间戳权重：图谱中的每条边都应包含 updated_at 属性。检索时，基于时间的衰减函数会降低旧信息的权重。显式否定：如果提取器检测到否定情绪或状态变更，LLM 应生成 Cypher 语句来标记旧关系为“失效”（设置属性 active: false）并创建新关系，而不是直接物理删除。这保留了“用户曾经喜欢 Python”的历史事实 19。6. 检索策略：混合 GraphRAG当 AstrBot 需要回复用户时，如何从庞大的图谱中找到那“针尖般”的关键信息？我们采用混合检索策略。6.1 查询重写与意图识别用户的原始 Query 往往是模糊的（如“那件事怎么样了？”）。Step 1: 在 AstrBot 的 on_llm_request 钩子中，首先调用一个小模型，结合当前短期上下文，将 Query 重写为独立查询：“关于用户 A 上周提到的服务器部署问题的进展”。6.2 双路召回 (Dual-Path Recall)向量路（Semantic Search）：对重写后的 Query 进行 Embedding。在 KuzuDB 中对 Entity 和 MemoryFragment 节点进行向量相似度搜索 (CALL db.index.query_nodes(...))。召回 Top-K 个最相关的实体节点。关键字路（Keyword Search）：对 Query 进行关键词提取。利用 KuzuDB 的全文索引（FTS）搜索匹配的节点名称。6.3 图遍历与上下文扩展 (Graph Traversal)单纯找到实体是不够的，我们需要上下文。Step 2: 以召回的 Top-K 节点为起点，向外进行 1-2 跳（Hop） 的遍历。获取与实体相连的 MemoryFragment（记忆片段）。获取与实体相连的最近的 Message（原始对话）。获取与实体相连的 User（谁提到的）。这种遍历能够捕捉到“隐式关联”。例如，搜索“数据库”，可能通过图谱路径 (数据库)-->(KuzuDB)<--(消息) 找到相关的讨论记录 20。6.4 上下文重排序与注入Step 3: 对收集到的所有节点和边进行去重和重排序（Reranking）。排序依据包括：语义相似度分数、时间衰减因子（越近越重要）、节点度中心性（越核心的概念越重要）。Step 4: 将最终筛选出的 Top-N 条信息格式化为自然语言文本块：[长期记忆检索]关于“数据库”：用户 A 在 10月5日 提到推荐使用 KuzuDB。关于“部署”：用户 B 曾在群里分享过 Docker Compose 配置。Step 5: 将此文本块插入到 AstrBot 发送给 LLM 的 System Prompt 的末尾。7. AstrBot 插件开发实战规范本节提供基于 AstrBot SDK 的具体实现代码结构。7.1 项目结构astrbot_plugin_infinite_memory/├── init.py           # 插件入口，注册类├── main.py               # 核心逻辑，事件监听├── config.py             # 配置定义├── graph_store.py        # KuzuDB 操作封装├── extractor.py          # LLM 抽取逻辑封装├── prompts.py            # Prompt 模板├── schema/               # 图谱初始化脚本│   └── init.cypher└── requirements.txt      # 依赖：kuzu, numpy, openai7.2 核心类实现 (main.py)Pythonfrom astrbot.api.all import *
from astrbot.api.event import filter
from.graph_store import GraphStore
from.extractor import Extractor
import asyncio

@register("infinite_memory", "YourName", "GraphRAG based infinite memory", "0.1.0")
class InfiniteMemoryPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        # 初始化图数据库路径，确保挂载在持久化目录
        db_path = config.get("db_path", "data/plugins/infinite_memory/kuzu_db")
        self.store = GraphStore(db_path)
        # 复用 AstrBot 的 LLM Provider，避免重复配置 Key
        self.extractor = Extractor(context.get_llm_provider(), config)

    # ---------------------------
    # 异步写入流 (Write Path)
    # ---------------------------
    @filter.event_message_type(filter.MessageType.TEXT)
    async def on_message(self, event: AstrMessageEvent):
        """
        监听所有文本消息，异步触发记忆摄入
        """
        message = event.message_obj
        session_id = event.session_id
        
        # 忽略自身消息
        if message.sender.user_id == self.context.robot_id:
            return

        # 使用 asyncio.create_task 确保不阻塞 AstrBot 主回复线程
        asyncio.create_task(
            self.process_ingestion(
                user_id=message.sender.user_id,
                user_name=message.sender.nickname,
                session_id=session_id,
                content=event.message_str,
                platform=event.platform_name
            )
        )

    async def process_ingestion(self, user_id, user_name, session_id, content, platform):
        # 1. 抽取实体和三元组
        triples = await self.extractor.extract(content)
        # 2. 计算向量 (Embedding)
        vector = await self.extractor.embed(content)
        # 3. 写入 KuzuDB
        self.store.add_memory(user_id, user_name, session_id, content, triples, vector)

    # ---------------------------
    # 同步读取流 (Read Path)
    # ---------------------------
    @filter.on_llm_request()
    async def on_llm_request(self, event: LLMRequestEvent):
        """
        在发送给 LLM 之前，拦截请求，注入长期记忆
        """
        query = event.prompt
        session_id = event.session_id # 获取当前会话 ID 以实现隔离

        # 1. 混合检索
        memories = self.store.search(
            query=query, 
            session_id=session_id, 
            limit=5
        )

        if memories:
            # 2. 构建 Prompt 上下文
            memory_text = "\n".join([f"- {m['summary']} (时间: {m['date']})" for m in memories])
            system_inject = f"\n\n【长期记忆参考】:\n{memory_text}\n请利用上述记忆辅助回答，若无关则忽略。"
            
            # 3. 注入 System Prompt
            # 注意：需检查 event.system_prompt 是否为空并追加
            if event.system_prompt:
                event.system_prompt += system_inject
            else:
                event.system_prompt = system_inject
7.3 KuzuDB 操作封装 (graph_store.py)Pythonimport kuzu
import time

class GraphStore:
    def __init__(self, db_path):
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        # 初始化节点和边表，向量索引
        # 略... (参考上文 DDL)
        pass

    def add_memory(self, user_id, user_name, session_id, content, triples, vector):
        # 1. 确保 Session 节点存在 (多租户隔离)
        self.conn.execute(
            "MERGE (s:Session {id: $sid})", {"sid": session_id}
        )
        # 2. 插入消息和向量
        self.conn.execute(
            """
            CREATE (m:Message {id: $mid, content: $content, timestamp: $ts, embedding: $vec})
            WITH m
            MATCH (s:Session {id: $sid})
            CREATE (m)-->(s)
            """,
            {
                "mid": generate_uuid(),
                "content": content,
                "ts": int(time.time()),
                "vec": vector,
                "sid": session_id
            }
        )
        # 3. 插入抽取的实体和关系 (循环处理 triples)
        #...
8. 多租户、隐私与安全策略在群聊场景中，数据隔离是绝对的硬性要求。AstrBot 作为一个跨平台机器人，可能同时服务于“Python 交流群”和“家庭群”。8.1 严格的数据隔离Session-Level Isolation: 所有的检索查询（Search Query）必须强制包含 WHERE session.id = $current_session_id 子句。Private vs Group: 私聊的记忆不应在群聊中被触发。在 graph_store.py 中，方法签名应强制要求传入 context_type（私聊/群聊）和 context_id，并在底层 Cypher 查询中做物理隔离逻辑。8.2 数据存储安全本地存储: KuzuDB 数据文件存储在本地磁盘。对于 Docker 部署，必须将数据目录 /data 映射到宿主机卷，以防容器重建导致记忆丢失。敏感信息过滤: 在 extractor.py 中，可以增加一个 PII（个人身份信息）过滤层，防止 LLM 将手机号、密码等敏感信息作为 Entity 存入图谱。
9. 部署运维与性能评估9.1 Docker 部署配置对于使用 Docker 部署 AstrBot 的用户，需要在 docker-compose.yml 中做如下配置，以确保 KuzuDB 数据的持久化：YAMLservices:
  astrbot:
    image: astrbotdevs/astrbot:latest
    volumes:
      -./data/plugins/astrbot_plugin_infinite_memory:/AstrBot/data/plugins/astrbot_plugin_infinite_memory
    environment:
      - KUZU_BUFFER_POOL_SIZE=1GB # 限制 KuzuDB 内存使用
9.2 性能开销分析延迟: 由于写入是异步的，用户感知的回复延迟仅增加 检索（Retrieval） 的时间。KuzuDB 的向量搜索在百万级数据下通常在 50ms 以内，加上 LLM Prompt 注入带来的额外 token 生成时间，总体延迟增加可控制在 500ms 内。成本:抽取成本: 这是最大的开销来源。建议设置 filter，仅对长度超过 10 个字符且包含实词的消息进行抽取。使用 gpt-4o-mini 或 DeepSeek-V3 等高性价比模型。存储成本: KuzuDB 采用列式压缩存储，文本和向量的存储效率很高，GB 级磁盘空间可存储数百万条对话记忆。
10. 结论与展望本报告提出的基于 KuzuDB 和 GraphRAG 的 AstrBot 无限记忆插件方案，从根本上解决了传统 Vector RAG 在对话场景下的语义断层和推理能力缺失问题。通过嵌入式图数据库、异步增量抽取和混合检索三大核心技术支柱，我们能够在保持 AstrBot 轻量、易部署特性的同时，赋予其接近人类的长期记忆能力。该方案不仅满足了“保留长期记忆”和“无限对话”的基本需求，还通过严格的 Schema 设计实现了多租户隔离，完美适配私聊与群聊并存的复杂场景。未来，该架构还可以进一步扩展，支持**代理反思（Agent Reflection）**机制，即机器人定期回顾图谱中的记忆，主动修正错误认知，从而实现真正具备自我进化能力的智能伴侣。注：本报告中涉及的所有代码片段均为示例性质，实际开发中需结合 AstrBot 最新 API 文档进行适配。引用的技术方案基于当前（2025年）图数据库与 LLM 的最佳实践。