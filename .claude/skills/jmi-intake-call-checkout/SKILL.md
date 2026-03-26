---
name: jmi-intake-call-checkout
description: 对 Jaymart/JMI 车险电话报案（FNOL intake）做四项核对（保单号、姓名电话、车牌车型、事故日在保险期内），并据通话与保单判断是否存在紧急情况、是否建议派调查员（surveyor）现场勘察（对齐现场勘察判断逻辑/加权矩阵与例外）；输入为通话记录与保单 Markdown；最终回复必须为单一 UTF-8 JSON 对象，且键名、类型、枚举、`items` 顺序与 `name_zh`/`name_en` 须与 references/output-schema.md 完全一致（规范级，非建议）；无 Markdown 围栏与前后文；HTTP API 可使用 structured_output_profile=jmi_intake_call_checkout 校验。用于 intake checkout、报案质检、955 初核。
---

# JMI Intake Call Checkout

## 输出契约（机器可读，必须遵守）

- **只输出一个 JSON 对象**：从第一个 `{` 到最后一个 `}` 即为完整结果；不要在 JSON 前后写任何自然语言、标题、列表或「如下」等说明。  
- **禁止使用 Markdown 代码围栏**（不要输出带语言标签的三反引号代码块）。  
- **形状唯一来源**：全文必须符合 [references/output-schema.md](references/output-schema.md) 中的表格与枚举——包括根键集合、`items` **四条顺序**及每条固定的 `name_zh` / `name_en`、`emergency_and_surveyor` 全部必填键；**禁止**在根、`items` 元素、`emergency_and_surveyor` 上使用文档未列出的键名（否则 API 校验失败）。`call_evidence` / `policy_evidence` 内键可随事实填充。  
- **调用方**：`POST /v1/agent/messages` 附加 `structured_output_profile=jmi_intake_call_checkout` 时，服务端按该规范做 Pydantic 校验；`structured_valid=true` 表示与 `output-schema.md` 对齐，否则见 `structured_error`（`final_answer` 保留原文）。

## 输入（向用户索取）

- **通话记录**：Markdown 或纯文本，含客服与客户轮次对话。  
- **保单**：Markdown 或结构化文本（至少含保单号、被保险人姓名泰/英、电话、车牌、品牌型号、保险起止日期；若有车辆用途/价值线索可一并用于「保单特殊性」因子）。  

可选：`case_reference`（案件号/文件夹名）；若仓库内有 `现场勘察判断逻辑.md`，可在 `source_documents` 中引用路径。

## 工作流

1. 阅读 [references/intake-checklist.md](references/intake-checklist.md)，明确四项含义与 `system_verification_required` 边界。  
2. 从通话记录抽取：保单号、姓名、电话、车牌、车型、事故日期时间（公历）、地点、**事故类型**（单方/双方、碰撞对象）、**人员伤亡**（显式或隐含）、**损失描述**（部位、是否提金额）、**现场与车辆状态**（是否已移动、是否仍接近事发地）、**客户是否要求现场**等。  
3. 从保单抽取同名字段，做归一化比对（泰文牌、英文姓名大小写、电话格式）。  
4. 事故日是否在 `[period_start, period_end]` 内（按保单所写日历日）。  
5. **紧急情况与派员**：阅读 [references/surveyor-dispatch-logic.md](references/surveyor-dispatch-logic.md)。先应用**快速触发/否决**规则；信息允许时再按**七因子**打分并映射阈值（≥8 `required`，5–7 `discretionary`，<5 `not_required`）。通话未提及的损失金额、事故方数等记入 `emergency_and_surveyor.data_gaps`，派员结论可 `discretionary` 并说明缺项。  
6. 逐条对照 [references/output-schema.md](references/output-schema.md) 构建 JSON（含 `items` 顺序与固定 `name_zh`/`name_en`），并 **仅** 将该对象作为助手回复全文。`emergency_and_surveyor` 须含规范所列全部键；`overall_result` 仅由四项核对决定，不因派员结论改为 `fail`。

## 规则

- 不臆造通话或保单未出现的内容；缺失写进 `notes` 或 `result: needs_review` / `data_gaps`。  
- 泰文车牌与字母易混时：结论写 `partial` 或 `needs_review` 并说明依赖人工看原件/系统车牌库。  
- 保单「有效性」除期间外，须提示核心系统查询的，统一在相关 `notes` 标注。  
- **紧急**与**派员**可不一致（例如：非紧急但责任争议需勘察）；在 `rationale_zh` 中写清逻辑。  
- 单方轻微、无伤亡、责任明确且现场已无法勘察时，典型输出 `is_emergency: false`、`dispatch_surveyor: not_required`，并列出远程定损选项。

## 资源

- `references/intake-checklist.md` — 四项定义与比对要点  
- `references/surveyor-dispatch-logic.md` — 紧急情形、派员阈值、加权因子与例外（摘要）  
- `references/output-schema.md` — JSON **规范性**结构（键、顺序、枚举；与 API 校验一致）  
