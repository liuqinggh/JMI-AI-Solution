---
name: local-rag
description: >
  在本地 Obsidian Vault 或任意 Markdown 知识库目录中进行检索和问答。
  当用户要求“搜索笔记”“查找知识库”“在文档中查找”“查一下笔记里”“vault 搜索”“从某个目录里找 Markdown 内容”时使用。
  如果用户明确提供路径，则使用用户路径；否则使用默认 Vault 路径。
  仅支持 Markdown 文档，采用目录路由 + 索引/MOC 导航 + 渐进式 grep/read 检索，避免全库盲搜和整文件加载。
---

# Local RAG - Markdown Knowledge Retrieval

## Scope

- 只处理 Markdown 文档：`.md`
- 默认 Vault 路径：`/Users/cd-la-067/project/Igloo-ai/iglooTech`
- 用户提供了目录路径时，必须优先使用用户路径
- 不处理 PDF、Excel、图片、二进制附件

## Directory Selection

### 1. Confirm the knowledge root

- 如果用户明确给了路径，例如“在 `./docs` 里查”或“帮我搜索 `/data/notes`”，直接使用该路径
- 如果用户没有给路径，使用默认路径：`/Users/cd-la-067/project/Igloo-ai/iglooTech`
- 必须先显式检查目录是否存在，再开始检索
- 如果用户给的路径不存在，明确告知并请用户重新指定，不要自行猜测别的目录
- 如果默认路径不存在，也要明确告知，而不是扫描其他目录兜底

### 2. Restrict the search space

- 只在确认存在的根目录下检索 `*.md`
- 默认排除这些高噪声路径：
  - `.git/`
  - `.obsidian/`
  - `.cursor/`
  - `.claude/`
  - `.trash/`
  - `node_modules/`
  - `Assets/`
  - `Template/`

## Retrieval Workflow

### Step 1: Understand the question

先从用户问题提取这些信号：

- 主题关键词
- 文件名线索
- 目录线索
- 时间范围
- 输出类型

关键词优先拆成 3-8 个候选项，包括：

- 中文关键词
- 英文术语
- 常见缩写
- 同义词或上位词

### Step 2: Route by Obsidian structure

对于宽泛问题，不要直接全库搜索，先按目录语义路由：

- `00-Inbox/`：新收集、临时想法、草稿
- `01-Projects/`：项目文档、需求、实现记录
- `02-Areas/`：长期维护主题
- `03-Resources/`：资料、链接、参考内容
- `04-Periodic/`：周记、会议纪要、临时记录
- `05-Growth/`：学习、复盘、成长记录
- `06-Personal/`：个人领域资料
- `09-Archive/`：归档内容

如果问题已经暗示领域，例如“项目”“周报”“会议纪要”“投资”，先把检索范围压到对应目录。

### Step 3: Prefer index and MOC notes

在候选目录里，优先找“索引型”文档，而不是先扫正文：

- 文件名包含 `索引`
- 文件名包含 `Index`
- 文件名包含 `MOC`
- 目录入口文档，例如 `README.md`、`knowledge.md`
- 明显用于汇总链接的 Markdown

优先读取这些文档的前 80-200 行，判断：

- 当前目录有哪些核心文档
- 哪些子主题与用户问题最相关
- 是否存在 wikilink 可进一步跟进

如果索引文档已经给出明确候选文件，再进入这些候选文件做精读。

### Step 4: Progressive retrieval on Markdown only

对候选目录或候选文件执行渐进式检索：

1. 先用文件名匹配缩小范围
2. 再对候选 Markdown 做关键词搜索
3. 对命中结果只读取局部上下文
4. 仍不够时再扩大到同目录或相关链接文件

禁止行为：

- 第一步就整库通配读取
- 一次性读取整篇长文
- 在没有目录路由的情况下直接扫所有 Markdown

### Step 5: Iterate up to 5 rounds

最多进行 5 轮检索。每轮都要做下面的判断：

1. 当前关键词是否过宽或过窄
2. 当前目录是否选错
3. 是否应切换到索引文档、链接文档或相关笔记
4. 是否已有足够证据回答问题

如果首轮结果不理想，依次尝试：

- 同义词
- 英文术语或缩写
- 更具体的文件名线索
- 同目录下的索引文档
- 由 wikilink 或 tags 跳转到关联笔记

## Obsidian-Specific Signals

检索和排序时优先考虑这些信号：

- 文件名与问题直接匹配
- H1/H2 标题命中关键词
- 文档前部摘要或开头段落命中
- Obsidian `[[wikilink]]` 指向关系
- tags，例如 `#MOC`、`#技术索引`
- frontmatter 中的 `tags`、`aliases`、`title`

当候选文件很多时，优先级如下：

1. 文件名直接匹配
2. 索引/MOC 文档
3. 标题命中更多关键词的文档
4. 被索引文档直接链接到的文档
5. 普通正文文档

## Search Strategy

### Precise queries

用户给出明确术语、文件名、目录名时：

- 先按路径或文件名过滤
- 再做关键词搜索
- 最后读取命中附近内容

### Broad queries

用户问题较宽泛时：

1. 先判断属于哪个 Obsidian 顶层目录
2. 找该目录下的索引/MOC 文档
3. 从索引文档收集 1-5 个最可能相关的候选文件
4. 再进入候选文件做局部检索

### Cross-note traversal

如果单篇文档不足以回答，可以沿这些信号扩展：

- `[[wikilink]]`
- 同标签文档
- 同目录下被索引引用的文档

扩展时保持克制，每轮只新增少量候选文件，避免失控扩散。

## Reading Rules

- 默认只读取命中附近的局部段落
- 对索引/MOC 文档，只读开头和核心列表区块
- 对正文长文，优先读取标题附近和关键词命中附近
- 只有在文档明显较短且高度相关时，才考虑读取全文

## Answering Rules

- 先给结论，再给依据
- 尽量引用来源，格式为 `路径:行号` 或 `文件名 + 章节`
- 如果答案来自多个笔记，要明确区分哪些是事实，哪些是综合归纳
- 找不到时要直接说明“当前目录下未检索到足够信息”，不要臆造
- 如果信息不足但方向明确，可以告诉用户下一步建议提供什么：
  - 更具体的路径
  - 更具体的关键词
  - 文件名
  - 时间范围

## Practical Heuristics

- 对项目问题，优先看 `01-Projects/`
- 对方法论和技术主题，优先看 `02-Areas/`
- 对参考资料，优先看 `03-Resources/`
- 对周报、会议纪要、近期记录，优先看 `04-Periodic/`
- 对个人投资、健康、生活等问题，优先看 `06-Personal/`
- 对已经结束的主题，必要时再查 `09-Archive/`

## What This Skill Is Not

- 这不是向量数据库 RAG
- 这不是多格式知识库引擎
- 这是一个面向 Obsidian/Markdown 目录的零依赖渐进式检索 Skill

