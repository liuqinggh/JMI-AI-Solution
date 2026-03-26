---
name: jmi-fresh-claim-doc-check
description: 对 Jaymart/JMI 车险 fresh claim 初次提交材料按「检查点设置」七类做有无与逐项核对；结合保单 Markdown 交叉验证；对保单号、车架号/发动机号、电话、姓名、身份证、报案号等允许 OCR 导致的 1～2 位差异按 references/ocr-tolerance.md 处理（不直接 fail）。视觉识别用 image-by-intent 的 vision-curl.sh；输出 JSON。在用户给出理赔材料文件夹 + policy.md、要求理赔材料质检时使用。
---

# JMI Fresh Claim Document Check

## 输入（向用户索取）

- **材料目录**：含 PDF（单页或多页拆分）、必要时图片；典型为 `.image/case-*/` 或理赔打包目录。  
- **保单路径**：`policy.md` 或同等内容的 Markdown。  
- **可选**：`case_id`、已知的标准报案号（用于比对）。

## 工作流

1. 阅读 [references/claim-materials-checklist.md](references/claim-materials-checklist.md) 全表（与仓库 `docs/.../检查点设置.md` 中 fresh claim 七类材料对齐）。  
2. 列出目录内文件；按文件名与内容归类到清单 **1–7**。缺失类别在 JSON `material_presence` 标 `present: false`。  
3. **视觉识别**：对每份需读的 PDF/图片调用 **image-by-intent** 的脚本（勿整目录默认 prompt 一次过完即了事——按文档类型换意图，见下节）。  
   - 脚本路径（默认）：`~/.cursor/skills/image-by-intent/scripts/vision-curl.sh`  
   - 依赖：本机 LiteLLM（默认 `http://localhost:4000/v1`）、`jq`、`curl`；环境变量见 image-by-intent skill（`LITELLM_BASE_URL`、`LITELLM_MODEL`）。  
4. 从保单抽取比对字段，见 [references/policy-fields.md](references/policy-fields.md)。  
5. 交叉核对：同一事实（保单号、姓名、电话、身份证、车牌、VIN、发动机号、报案号、事故日、责任、免赔额）在多份材料间比对。字符类字段先按 [references/ocr-tolerance.md](references/ocr-tolerance.md) **归一化**并应用 **1～2 位 OCR 容差**：容差内用 `partial`（或 `pass`+notes），**不得**直接 `fail`；超出容差或事实类错误仍标 `fail` 并列入 `recommended_actions_zh`。  
6. 按 [references/output-schema.md](references/output-schema.md) 输出 **JSON**。

## vision-curl 用法（按类型换 prompt）

对**单个 PDF**（推荐）：

```bash
VISION_SH="$HOME/.cursor/skills/image-by-intent/scripts/vision-curl.sh"
"$VISION_SH" "/path/to/doc.pdf" "【中文意图】例如：提取报案号、保单号、被保险人、驾驶员、车牌、车架号、事故时间地点、责任判定、免赔额、所有签字与日期；未见写「未见」。"
```

- **陈述/FNOL 混排**：意图侧重笔录字段 + 签字日期。  
- **FCCS**：侧重报案号、保单号、事故时间地点、责任判定（错误方/正确方）、免赔额、勘察员签字。  
- **定损单**：侧重报案号、车牌、车架号、受损部位、责任是否与 FCCS 一致、定损日期、签字。  
- **驾驶员陈述书**：侧重理赔编号、是否被保险人本人、身份证号、驾照有效期、签字、日期。  
- **驾驶证**：侧重姓名、出生日期、身份证号、准驾、有效期、签发机关、「复印件正确」核签。  
- **登记证**：正反面分别提取；车牌、车架号、发动机号、品牌型号、车主、占有人、证件号、地址、官方签章。  
- **照片类 PDF**：按清单 **第 7 节** 逐项下结论（车牌、车损、多角度、VIN 特写、拍摄时间、数量、清晰度）。

若某路径下仅有图片无 PDF，可对单张图使用同一脚本传图片路径。

## 规则

- **OCR 容差**：见 [references/ocr-tolerance.md](references/ocr-tolerance.md)。保单号、VIN、发动机号、电话、泰/英姓名、身份证、报案号等与保单或其他材料比对时，归一化后 **编辑距离 ≤2** 按容差处理；≥3 或责任/日期/金额错误仍 `fail`。  
- 泰文车牌、佛历日期易错：车牌可结合 VIN 佐证；日期不按「字符位」容差，按日历事实判断。  
- **VIN 与发动机号**与保单在容差内一致时，可认定「同一标的」；在 `notes` 中记录是否启用容差。  
- 不得在 JSON 中伪造未从材料或保单出现的数据。

## 资源

- `references/claim-materials-checklist.md` — 材料类别与子检查项  
- `references/ocr-tolerance.md` — OCR 1～2 位差异比对规则与 JSON 记录建议  
- `references/policy-fields.md` — 保单抽取字段表  
- `references/output-schema.md` — JSON 结构约定  
