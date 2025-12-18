# GraphMemory 变更日志

## [0.4.0] - 2025-12-18

### 新增功能

#### 管理指令
- **`/memory_search`** - 搜索图谱中的实体
  - 支持关键词搜索
  - 支持实体类型过滤
  - 支持结果数量限制
  - 显示实体的描述、重要性、访问次数和关系

- **`/memory_forget`** - 删除指定的实体
  - 需要 `confirm:yes` 参数确认删除
  - 自动删除相关的所有关系
  - 显示删除的关系数量

- **`/memory_export`** - 导出图谱数据为 JSON 格式
  - 支持导出所有数据或指定人格的数据
  - 导出实体、关系和会话信息
  - 自动保存到插件数据目录

- **`/memory_import`** - 从 JSON 文件导入图谱数据
  - 支持合并模式和覆盖模式
  - 显示导入的实体和关系数量
  - 自动处理数据冲突

#### 主动记忆检索（Function Calling）
- **`search_memory` 工具** - LLM 可主动调用的记忆检索工具
  - 支持关键词、类型过滤和结果数量限制
  - 返回实体及其关系的 JSON 格式数据
  - 需要 LLM 支持 Function Calling
  - 通过配置 `enable_function_calling` 启用

#### 实体消歧和合并
- **自动识别相似实体** - 基于向量相似度
  - 可配置相似度阈值（默认 0.85）
  - 只比较相同类型的实体
  - 按重要性优先处理

- **智能合并实体** - 使用 LLM 判断
  - 合并实体的重要性和访问次数
  - 转移所有关系到保留的实体
  - 自动处理关系冲突和合并

- **定期自动消歧** - 集成到维护循环
  - 可配置消歧间隔（默认 7200 秒）
  - 通过配置 `enable_entity_disambiguation` 启用
  - 记录消歧结果和统计信息

- **`/memory_disambiguate`** - 手动触发实体消歧
  - 支持自定义相似度阈值（`threshold:<0-1>`）
  - 支持自动合并模式（`auto_merge:true|false`）
  - 显示找到的相似实体对和合并结果
  - 默认使用 LLM 判断是否合并

#### 检索算法优化
- **加权混合检索** - 可配置向量和关键词权重
  - 向量检索权重：默认 0.7
  - 关键词检索权重：默认 0.3
  - 同时命中两种检索的实体额外加分 20%

- **智能重排序** - 综合多个因素
  - 检索分数权重：60%
  - 实体重要性权重：30%
  - 访问频率权重：10%
  - 考虑时间衰减（通过 importance 体现）

- **可配置权重** - 新增配置项
  - `vector_search_weight`: 向量检索权重
  - `keyword_search_weight`: 关键词检索权重

### 核心功能
- 在 `GraphStore` 中添加了搜索、删除、导出、导入方法
- 创建了 `FunctionCallingHandler` 处理 Function Calling
- 创建了 `EntityDisambiguation` 处理实体消歧
- 创建了 `CommandHandler` 分离指令处理逻辑
- 优化了 `MemoryRetriever` 的检索和排序算法

### 改进
- **代码架构优化** - 分离关注点
  - `main.py` 只负责注册，不包含业务逻辑
  - `command_handler.py` 处理所有指令逻辑
  - 提高代码可维护性和可测试性

- 完善了关系信息的格式化输出
- 改进了错误处理和日志记录
- 优化了代码结构和注释

### 配置更新
新增 4 个配置项：
- `enable_entity_disambiguation`: 启用实体消歧（默认 false）
- `disambiguation_interval`: 实体消歧间隔（默认 7200 秒）
- `vector_search_weight`: 向量检索权重（默认 0.7）
- `keyword_search_weight`: 关键词检索权重（默认 0.3）

### 文档
- 创建了 v0.4.0 开发计划文档
- 更新了版本号和描述
- 更新了 CHANGELOG.md

---

## [0.3.1] - 2025-12-18

### 修复
- **修复嵌套事件循环问题** (`graph_store.py:147-149`)
  - 将 `asyncio.run()` 改为在异步上下文中直接 `await`
  - 避免了 "RuntimeError: This event loop is already running" 错误

### 改进
- **完善记忆检索器的关系信息格式化**
  - 实现了 `_get_relations_between_entities()` 方法
  - 在记忆上下文中显示实体间的关系

- **优化 Prompt 模板**
  - 知识提取 Prompt 更加详细和结构化
  - 查询重写 Prompt 添加了示例和规则说明

### 文档
- 创建了详细的测试计划文档
- 更新了版本号到 0.3.0

---

## [0.3.0] - 2025-12-18

### 重大更新
完全重新设计和实现的版本，采用全新的简化架构。

### 新架构
- **2层记忆系统**
  - 缓冲区（MemoryBuffer）：短期记忆
  - 图谱（GraphStore）：长期记忆

- **简化的 Schema**
  - 3种节点类型：User, Session, Entity
  - 4种关系类型：PARTICIPATED_IN, RELATED_TO, MENTIONED_IN, KNOWS

### 核心功能
- **自动知识提取**
  - 从对话中提取实体和关系
  - 支持增量更新
  - 实体重要性计算

- **智能记忆检索**
  - 向量 + 关键词混合检索
  - 人格过滤（分层共享策略）
  - 结果排序和格式化

- **被动记忆注入**
  - LLM 请求前自动注入
  - 查询重写提升准确性
  - 格式化输出

- **人格分层共享**
  - 自动获取当前人格ID
  - 人格切换检测
  - 检索时过滤当前人格相关记忆

- **时间衰减机制**
  - 定期衰减实体重要性和关系强度
  - 清理低重要性实体
  - 访问时增强重要性

### 核心模块
- `core/schema.py` - Schema 定义
- `core/entities.py` - 数据实体
- `core/prompts.py` - Prompt 模板
- `core/memory_buffer.py` - 消息缓冲
- `core/knowledge_extractor.py` - 知识提取
- `core/graph_store.py` - 图数据库
- `core/memory_retriever.py` - 记忆检索
- `core/manager.py` - 核心管理器

### 配置
- 14 个配置项（简化 30%）
- 支持私聊/群聊分别配置缓冲区大小
- 支持查询重写、时间衰减等高级功能

### 指令
- `/memory_stat` - 显示图谱统计信息

---

## [0.2.1] - 之前版本

旧版本，已废弃。

---

**版本格式**: [主版本.次版本.修订版本]
**日期格式**: YYYY-MM-DD
