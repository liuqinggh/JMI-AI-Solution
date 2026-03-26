在 **Claude Agent SDK + Skills** 的应用场景下，处理文件（尤其是图片、PDF 等非纯文本文件）主要依赖以下几种机制，结合 Anthropic 的原生能力、Agent 工具链和自定义 Skills 来实现高效处理。以下是详细说明（基于 Claude 的最新文档和 Agent 生态）：

### 1. **原生文件上传与多模态处理（无需 Skills 时）**

Claude API（包括 Agent SDK 底层）本身支持直接处理图片和 PDF：

- **图片（Images）**：

  - 支持 JPEG、PNG、GIF、WEBP 等格式。
  - 处理方式：直接在 Messages API 中以 `image` content block 上传（base64 或 Files API 的 `file_id`）。
  - Claude 使用 Vision 能力分析图像内容、描述、OCR、图表理解等。
  - 在 Agent SDK 中，Agent 可以读取工作目录中的图片文件（通过内置 **Read** 工具），或通过 Bash 工具处理（例如用 ImageMagick 转换格式）。
- **PDF 文件**：

  - Claude（尤其是 3.5+ 模型，如 Sonnet/Opus）原生支持 PDF。
  - 处理流程：
    1. 系统自动将 PDF 每页转换为图像（利用 Vision）。
    2. 同时提取文本（text extraction）。
    3. Claude 同时分析文本 + 图像，能理解图表、表格、图片、公式等视觉元素。
  - 限制：单文件通常 ≤30MB，页数有上限（例如 100 页左右，视模型而定）。
  - 在 Agent SDK 中：Agent 可通过 **Read** 工具读取 PDF 文件内容，或结合 **Bash** 工具运行外部命令（如 `pdftotext`、`pdfimages`）进一步处理。

上传方式（API/SDK 示例）：

- 直接在消息中附带文件（`document` 或 `image` block）。
- 使用 **Files API**：先上传文件获取 `file_id`，后续消息中引用（适合多轮 Agent 对话，避免重复上传）。

### 2. **Agent SDK 中的文件系统与工具支持**

Claude Agent SDK（原 Claude Code SDK）提供了一个完整的 Agent 环境，文件处理更像“本地计算机”操作：

- **内置工具**（无需额外开发）：

  - **Read**：读取工作目录中任意文件（包括图片、PDF 的原始内容或元数据）。
  - **Write/Edit**：创建或修改文件（例如从 PDF 提取数据后生成新报告）。
  - **Bash**：运行终端命令，非常强大。例如：
    - 处理 PDF：`pdftotext file.pdf output.txt`、用 `pdf2image` 转图片、`pdftk` 合并/拆分 PDF。
    - 处理图片：用 `convert`（ImageMagick）、`pillow`（Python）进行裁剪、OCR（结合 tesseract）等。
  - **Glob/Grep**：搜索文件或内容。
  - **Code Execution**（在某些 beta 工具中）：支持特定文件类型分析。
- Agent 循环：Agent 会自主决定使用哪个工具。例如，用户说“分析这个 PDF 中的图表并生成报告”，Agent 可能先 Read PDF → Bash 提取 → 分析 → Write 新文件。

这在实际应用场景（如文档自动化、报告生成、数据提取）中非常灵活，因为 Bash 能调用系统已安装的库/命令。

### 3. **Skills（技能）机制 —— 专门用于复杂文件处理场景**

Skills 是 Claude Agent 生态的核心扩展方式，特别适合“专业化”文件处理。它本质上是文件系统中的一个文件夹（包含 `SKILL.md` + 可选脚本/资源），Agent 会根据任务自动发现并加载。

- **预置 Agent Skills**（Anthropic 官方提供）：

  - **pdf**：提取文本/表格、填充表单、合并/拆分文档、生成新 PDF。
  - **docx / xlsx / pptx**：类似，支持创建、编辑、分析 Office 文件。
  - 使用时：在 API 请求的 `container` 参数中指定 `skill_id: "pdf"` 等，结合 code-execution tool。
  - 输出：Skills 可生成文件，返回 `file_id`，再用 Files API 下载。
- **自定义 Skills**（推荐用于你的应用场景）：

  - 结构示例（PDF 处理 Skill）：
    ```
    skills/pdf-processing/
    ├── SKILL.md          # 核心：YAML 元数据 + 详细指令、提示词、工作流
    ├── scripts/
    │   └── parse_pdf.py  # Python 脚本（用 pdfplumber、PyMuPDF、pypdf 等）
    ├── references/       # 参考文档、模板
    └── assets/           # 模板文件、字体等
    ```
  - **SKILL.md** 中定义：
    - description：何时触发（如“处理 PDF 时自动使用”）。
    - 指令：详细的工作流（提取文本 → 分析图像 → 生成报告）。
    - 引用脚本：Agent 需要时才加载（避免上下文过长）。
  - 处理流程：
    1. Agent 根据用户查询匹配 Skill 描述，加载 SKILL.md。
    2. 执行内部脚本或 Bash（例如 Python 处理 PDF 中的图片/表格）。
    3. 对于图片：Skill 可调用 Vision 分析，或脚本转格式后让 Claude 看。
    4. 输出：生成新文件（PDF/图片/报告），Agent 可进一步处理或返回给用户。
- **在 Agent SDK 中的集成**：

  - Skills 放在 `.claude/skills/` 目录（或通过 setting_sources 配置）。
  - Agent 启动时加载 Skill 元数据，按需注入完整内容。
  - 优势：无限知识容量（脚本可处理大文件）、一致性（专业任务标准化）、动态加载（不占上下文）。

应用场景示例：

- **PDF 发票处理**：上传 PDF → pdf Skill 提取文本+图像 → 分析金额/图表 → 生成 Excel 报告。
- **图片批量处理**：自定义 Skill 用脚本识别图像内容，结合 Vision 生成描述或编辑。
- **文档自动化工作流**：结合多个 Skills（pdf + xlsx），从 PDF 提取数据 → 分析 → 生成 PPT。

### 4. **实际开发建议（Claude Agent SDK + Skills）**

1. **简单场景**：直接用原生 PDF/Vision + Agent 内置工具（Read/Bash）。
2. **复杂/重复场景**：创建自定义 pdf-processing Skill，里面放处理脚本。
3. **API 调用**：在 Messages 请求中启用 beta headers（如 `code-execution-2025-08-25`），指定 skills。
4. **文件持久化**：用 Files API 管理上传/下载；Agent 工作目录支持读写。
5. **注意事项**：
   - PDF 中的图片依赖 Vision，可能有幻觉风险（复杂图表需仔细 prompt）。
   - 大文件建议分块或用 Bash 预处理。
   - 在 Claude.ai / Claude Code 中，也支持直接拖拽文件 + Skills。

如果你的具体场景是“自动化提取 PDF 中的图片并分析”或“生成带图表的报告”，可以提供更多细节，我可以帮你给出 SKILL.md 示例或代码片段。总体来说，**Skills + Bash + 原生 Vision/PDF 支持** 是最强大且灵活的组合，能覆盖绝大多数文件处理需求。
