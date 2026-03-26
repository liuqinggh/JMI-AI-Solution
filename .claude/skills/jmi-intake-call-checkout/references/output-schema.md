# JSON 输出结构（规范，须严格遵守）

本文档为 **唯一合法的输出形状**：根对象键名、类型、`items` 四项顺序与 `name_zh` / `name_en`、`overall_result` / `result` / `dispatch_surveyor` 枚举取值，均须一致；**不得**在根、`items[]` 各元素、`emergency_and_surveyor` 上擅自增删键名或改用同义字段名。`call_evidence` / `policy_evidence` 为对象即可，键名由内容决定。

## 输出契约（与 API 一致）

- 模型/Agent **最终回复正文 = 仅一个 JSON 对象**（可美化换行）；禁止 Markdown 代码围栏与前言后语。  
- 客户端调用 `POST /v1/agent/messages` 时可传 `structured_output_profile=jmi_intake_call_checkout`：服务端默认将 `final_answer` 设为 **仅最后一轮助手文本**（`final_answer_text_policy=last_assistant_turn`），避免多轮中间说明拼进解析串；仍可用表单字段 `final_answer_text_policy=full` 强制保留全量。随后对 `final_answer` 做 JSON 抽取与 **按本规范的 Pydantic 校验**；校验失败时 `structured_valid=false`。  
- 若模型误加 Markdown 代码块，服务端会尝试剥除后再解析；仍应尽量直接输出裸 JSON。

## 根对象：键与约束

| 键 | 必填 | 类型 / 取值 |
|----|------|----------------|
| `case_reference` | 是 | `string`（案件号、文件夹名等；无则 `""`） |
| `checklist` | 是 | 字面量 `"intake_call_checkout"` |
| `source_documents` | 是 | `string[]`（通话、保单及所用参考文档路径） |
| `overall_result` | 是 | `"pass"` \| `"fail"` \| `"partial"`（**仅**由四项 `items` 核对决定） |
| `summary` | 是 | `string`（一两句中文，可含派员结论摘要） |
| `items` | 是 | 长度 **4** 的数组，**顺序与下表一致** |
| `emergency_and_surveyor` | 是 | 对象，见下文 |
| `observations_outside_checklist` | 否 | `null` 或 `{ "topic", "detail" }[]` |

## `items[]`：顺序与固定命名（与 intake 清单一一对应）

下表顺序即为 JSON 数组 **从下标 0 到 3** 的必填顺序；每条须含 `sequence`、`name_zh`、`name_en`、`result`、`call_evidence`、`policy_evidence`、`notes`。

| `sequence` | `name_zh`（须完全一致） | `name_en`（须完全一致） |
|------------|-------------------------|-------------------------|
| 1 | 保单号和有效性 | `policy_number_and_validity` |
| 2 | 姓名和联系电话一致性 | `name_and_phone_consistency` |
| 3 | 车牌号和车型一致性 | `plate_and_vehicle_model_consistency` |
| 4 | 事故日期是否在保单有效期内 | `loss_date_within_policy_period` |

每项字段：

- `sequence`：`1`–`4`，且与数组位置一致（第 1 条为 `1`，依此类推）  
- `name_zh`、`name_en`：与上表一致  
- `result`：`"pass"` \| `"fail"` \| `"partial"` \| `"needs_review"`  
- `call_evidence`：`object`  
- `policy_evidence`：`object`  
- `notes`：`string`  

## `emergency_and_surveyor`（紧急情况与调查员）

`**必填**`，键名如下（**均为必填键**；值为 `null` 的仅 `weighted_total_score`、`score_breakdown`）：

- `is_emergency`：`boolean`  
- `emergency_reasons_zh`：`string[]`  
- `dispatch_surveyor`：`"required"` \| `"not_required"` \| `"discretionary"`  
- `weighted_total_score`：`number` \| `null`（无法算全因子时为 `null`）  
- `score_breakdown`：`object` \| `null`；若提供对象，键**建议**与加权矩阵一致：`accident_nature`、`loss_amount`、`liability_complexity`、`casualties`、`scene_status`、`fraud_risk`、`policy_special`，值为文档表格范围内的**整数**或 `null`  
- `rationale_zh`：`string`  
- `remote_survey_options_zh`：`string[]`  
- `exceptions_considered_zh`：`string`  
- `data_gaps`：`string[]`  

`overall_result` 仍仅由四项 intake **核对**决定；`emergency_and_surveyor` 为并行结论，**不得**据此修改 `overall_result`。

## `observations_outside_checklist`（可选）

若存在，每项为对象：

- `topic`：`string`  
- `detail`：`string`  
