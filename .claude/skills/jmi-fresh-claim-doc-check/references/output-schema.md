# JSON 输出结构（建议）

- `case_id`：案件/FNOL 标识  
- `checklist`：固定 `"fresh_claim_documents"`  
- `reference_policy`：保单文件路径  
- `vision_pipeline`：对象，含 `tool`（如 `image-by-intent`）、`script` 绝对路径、`litellm_base_url`、`model`、`note`（OCR 局限说明）  
- `policy_snapshot`：从保单抽取的键值（见 policy-fields.md）  
- `material_presence`：按材料类别 `present: true/false`，`source_files_hint`: 文件名数组（键或顺序对应清单 1–7）  
- `overall_result`：`pass` | `fail` | `partial`  
- `overall_summary_zh`：中文综述  
- `documents`：数组，与清单 **1–7** 一一对应；某类缺失仍保留该项，`result: fail`，`checks` 说明缺件  
- `recommended_actions_zh`：字符串数组，可执行补救建议  

`documents[]` 每项：

- `id`：**1–7**（与 `检查点设置.md` fresh claim 材料序号一致）  
- `name_zh`：与清单中文名一致（如「事故现场勘察报告 (FCCS)」）  
- `result`：`pass` | `fail` | `partial`  
- `checks`：子项数组，与 `claim-materials-checklist.md` 该节 bullet 对应；每项含 `item`、`result`、`evidence`、可选 `notes`  

`result` 判定习惯：任一关键子项 `fail` 则该文档类倾向 `fail`。对保单号、VIN、发动机号、电话、姓名、身份证、报案号等，若已按 `ocr-tolerance.md` 归一化且 **编辑距离 ≤2**，子项用 `partial` 或 `pass`，在 `notes` 中写 `ocr_tolerance`、`policy_value`、`document_value`（或编辑距离说明）；**不得**仅因 1～2 位 OCR 差异标 `fail`。责任判定、事故日期、免赔额金额等事实项不适用字符容差。
