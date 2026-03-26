# document-ocr-ai 开发说明

## 设计概要

- **目标**：对用户提供的图片/PDF 做 OCR，支持 KTP 及 axinan-prod 下多种 Document AI processor。
- **方案**：Python + `google-cloud-documentai`（放弃 curl/request.json）；认证用 ADC 或 `GOOGLE_APPLICATION_CREDENTIALS`。
- **入口**：`scripts/documentAI_sample.py`（`-f` 文件，`--ktp` 或 `-p` processor-id）；说明见 SKILL.md 与 references。

---

## 迭代记录

记录每次优化/修复/新增，**新条目写在下面表格首行下方**。

| 日期 | 类型 | 内容 | 涉及 |
|------|------|------|------|
| 2026-03-06 | 新增 | 预设 processor：`--preset <name>`，支持 death_certificate、medical_bill、police_report、traveloka_delay、traveloka_classifier、identifier_classifier；processor 表放入 references/document-ai-processors.md | documentAI_sample.py, SKILL.md, references/document-ai-processors.md, DEV_NOTES.md |
| 2026-03-06 | 修复 | credentials：同一套代码 ipynb 可跑、终端跑 .py 报 403；脚本内硬编码 `CREDENTIALS_PATH` 指向 gcloud ADC 文件，与 notebook 一致 | documentAI_sample.py, DEV_NOTES.md |
| 2026-03-06 | 文档 | DEV_NOTES 设计格式：设计概要 + 迭代记录 + 当前设计详情，便于后续记录优化迭代 | DEV_NOTES.md |
| 2026-03-06 | 方案调整 | 放弃 curl/request.json，统一用 Python 脚本；新增 `--ktp` 快捷参数 | SKILL.md, documentAI_sample.py, ktp-recognition.md, gcp-multi-project.md |
| 2026-03-06 | 文档 | 开发说明从 开发记录.log 迁入并结构化 | DEV_NOTES.md（原 开发记录.log） |

**类型**：`优化` / `修复` / `新增` / `文档` / `依赖` 等，可自拟。

---

## 当前设计详情

### 目标

- 对用户提供的图片或 PDF 做 OCR，提取全文或结构化实体。
- 支持 KTP（印尼身份证）及 axinan-prod 下其他 Document AI processor（如 Death Certificate、Medical Bill 等）。

### 方案选型

| 方案 | 结论 | 说明 |
|------|------|------|
| curl + request.json + gcloud token | **放弃** | 需手写 Base64、路径易错、403 时排查难；认证与 quota project 易混淆。 |
| **Python + google-cloud-documentai** | **采用** | 官方 SDK 走 ADC 或 `GOOGLE_APPLICATION_CREDENTIALS`，认证统一；本地读文件、自动 MIME，无需手写请求体。 |

### 目录与职责

- **SKILL.md**：入口说明、前置条件、脚本参数与流程；不写 curl/request 细节。
- **scripts/documentAI_sample.py**：单文件 OCR 入口；`-f` 文件，`-p` processor-id、`--ktp` 或 `--preset <name>`；输出 text/entities/both。
- **references/ktp-recognition.md**：KTP 专用说明（project/location/processor、脚本示例）。
- **references/document-ai-processors.md**：预设 processor 名称与 ID 表，供 `--preset` 使用。
- **references/gcp-multi-project.md**：axinan-prod vs axinan-dev 约定、ADC 与 quota project 说明。

### 设计要点

1. **KTP 快捷**：`--ktp` 固定 project `660077994974`、location `us`、processor `10dee3ae32570cdf`，避免每次手输。
2. **通用 processor**：通过 `-p <PROCESSOR_ID>` 支持任意 processor；默认 project/location 与 KTP 一致，可按需 `--project-id` / `--location` 覆盖。
3. **认证**：优先 gcloud ADC（`gcloud auth application-default login` + `gcloud config set project axinan-prod`）；临时可用 `GOOGLE_APPLICATION_CREDENTIALS` 指向 Service Account 密钥。
4. **依赖**：`google-cloud-documentai`；不依赖 OAuth client_secret 文件（该文件不能作为 ADC 密钥）。

### Credentials 情况与处理

- **现象**：同一套代码在 Jupyter/ipynb 里可正常调用 Document AI，在终端用 `python script.py` 跑则报 403（`documentai.processors.processOnline` denied）。
- **原因**：Notebook 内核与终端使用的**环境变量**不一致。常见情况：
  - **GOOGLE_APPLICATION_CREDENTIALS**：Notebook 可能通过 `.env` 或内核配置设置了该变量，指向有权限的 Service Account 密钥或 gcloud ADC 文件；终端未设置时，客户端会走默认 ADC 链（含 `~/.config/gcloud/application_default_credentials.json`），若该文件里的账号无 Document AI 权限则 403。
  - **GOOGLE_CLOUD_PROJECT**：若某处依赖“当前项目”，两边不一致也可能导致行为不同。
- **解决方法**：在 `documentAI_sample.py` 内**硬编码**凭证路径，与 notebook 一致，避免依赖终端环境：
  - 常量 `CREDENTIALS_PATH = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")`。
  - 在创建 `DocumentProcessorServiceClient()` 前，若该文件存在则设置 `os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(CREDENTIALS_PATH)`。
  - 这样无论终端是否已设该环境变量，脚本都固定使用 gcloud ADC 文件；若仍 403，说明该 ADC 账号在目标项目上无权限，需在 GCP IAM 中为该账号授予 Document AI 权限，或改用有权限的 Service Account 密钥（届时可改 `CREDENTIALS_PATH` 指向该 key 文件）。

### 后续可扩展

- 新增预设时：在 `references/document-ai-processors.md` 表中增加一行，并在 `scripts/documentAI_sample.py` 的 `PRESETS` 字典中增加对应项。
- 当前已支持预设：ktp、death_certificate、identifier_classifier、medical_bill、police_report、traveloka_delay、traveloka_classifier。
