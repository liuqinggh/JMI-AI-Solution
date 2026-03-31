# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI service that wraps the Claude Agent SDK, providing HTTP endpoints for multi-turn conversational AI with file upload support. The service is designed for insurance claim processing (JMI/Jaymart) with specialized skills for intake verification and document checking.

**Key capabilities:**
- Unified message API supporting both single-turn and multi-turn conversations
- File upload with content-addressed storage
- Session management using SDK-native session IDs
- Support for multiple Claude providers (Vertex AI, Bedrock, local proxy)
- Structured output validation for insurance workflows
- LangFuse integration for tracing and monitoring

## Development Commands

### Environment Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (using uv)
uv sync
```

### Running the Service

```bash
# Start development server with auto-reload
uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload

# Or use the main entry point
python main.py

# Or with uv
uv run python main.py
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_routes.py

# Run with verbose output
pytest -v

# Run tests with async support
pytest -v --asyncio-mode=auto
```

### API Testing

```bash
# Health check
curl http://localhost:8000/

# Get configuration info
curl http://localhost:8000/config

# Web test interface
open http://localhost:8000/test

# Send a message (new session)
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好，请介绍一下自己"

# Continue a conversation
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=我刚才问了什么？" \
  -F "session_id=<session_id_from_previous_response>"

# Upload files with message
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=请读取并总结这个文件" \
  -F "files=@test.txt"
```

## Architecture

### Design Principles

1. **Unified Message Flow**: Single endpoint (`POST /v1/agent/messages`) handles both new and continuing conversations. No separate single-turn vs multi-turn APIs.

2. **SDK-Native Sessions**: Session IDs come exclusively from Claude Agent SDK (`session_id` field in SDK messages). The service never generates its own session identifiers.

3. **Configuration-Driven**: All runtime parameters (model, tools, prompts, storage paths) come from `conf/config.yaml`, not hardcoded in Python.

4. **Content-Addressed Storage**: Files are stored by content hash to avoid duplication. Session directories contain symlinks to content-addressed files.

5. **Thin HTTP Layer**: FastAPI routes are minimal. Core logic lives in dedicated modules (`agent/`, `storage/`, `tracing/`).

### Key Components

**`src/config.py`**
- Loads `conf/config.yaml` using Pydantic models
- Sets environment variables for Claude Code CLI (`ANTHROPIC_BASE_URL`, etc.)
- Detects managed providers (Vertex AI, Bedrock) and skips local proxy injection

**`src/agent/executor.py`**
- Executes agent queries via Claude Agent SDK
- Parses message stream to extract `session_id`, `final_answer`, execution steps
- Handles both string prompts and multipart content (files)
- Supports two `final_answer_text_policy` modes:
  - `full`: Concatenates all assistant turns
  - `last_assistant_turn`: Returns only the last turn (useful for structured outputs)

**`src/agent/options.py`**
- Builds `ClaudeAgentOptions` from config
- Handles session resumption: sets `resume=session_id` when continuing
- Injects `output_format` for structured output validation

**`src/storage/content_store.py`**
- Content-addressed file storage (files stored by SHA-256 hash)
- Session directories contain symlinks to content store
- Supports pending → finalized workflow for new sessions

**`src/storage/file_store.py`**
- Legacy wrapper (may be refactored)
- Handles file sanitization and session directory management

**`src/api/routes.py`**
- Defines FastAPI endpoints
- Handles multipart/form-data for file uploads
- Integrates with LangFuse tracer for monitoring

**`src/tracing/langfuse_tracer.py`**
- Optional LangFuse integration for observability
- Logs agent execution events, message types, completions
- Controlled by `langfuse.enabled` in config

### Session and File Flow

**New session without files:**
1. Receive `prompt` (no `session_id`)
2. Build `ClaudeAgentOptions(continue_conversation=True)`
3. Execute query, extract SDK `session_id` from `TaskStartedMessage`/`ResultMessage`
4. Return `session_id` + `final_answer`

**New session with files:**
1. Receive `prompt` + `files`
2. Save files to content store, get hashes
3. Create pending session directory with symlinks
4. Execute query → get `session_id` from SDK
5. Finalize session directory: rename `.pending/<temp>` → `<session_id>`
6. Augment prompt to reference uploaded files
7. Return `session_id` + `final_answer`

**Continue session:**
1. Receive `prompt` + `session_id` (± optional new files)
2. Build `ClaudeAgentOptions(resume=session_id, continue_conversation=True)`
3. If new files: add to existing session directory
4. Execute query
5. Return same `session_id` + new `final_answer`

### Provider Configuration

**Local Proxy Mode:**
```yaml
sdk:
  base_url: http://localhost:4000
  api_key: sk-1234
  # env section commented out or omitted
```

**Vertex AI Mode:**
```yaml
sdk:
  env:
    CLAUDE_CODE_USE_VERTEX: "1"
    GOOGLE_APPLICATION_CREDENTIALS: /path/to/credentials.json
    ANTHROPIC_VERTEX_PROJECT_ID: your-project-id
    CLOUD_ML_REGION: global
```

Check active provider: `GET /config` returns `provider` field.

### Structured Output Profiles

For insurance workflows, the service supports validated structured outputs:

- `jmi_intake_call_checkout`: FNOL intake verification (4-point checklist + surveyor dispatch)
- `jmi_fresh_claim_doc_check`: Fresh claim document verification (7 categories)

Usage:
```bash
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=<insurance prompt>" \
  -F "structured_output_profile=jmi_intake_call_checkout"
```

Response includes:
- `structured_output`: Parsed JSON matching schema
- `structured_valid`: Boolean indicating schema compliance
- `structured_error`: Validation error if invalid

Schemas are defined in:
- `src/api/jmi_intake_checkout_output.py`
- `src/api/jmi_fresh_claim_doc_check_output.py`

Parsers strip Markdown code fences and validate against Pydantic models.

## Configuration

Configuration is in `conf/config.yaml`. Key sections:

**`app`**: Server settings (host, port, reload)

**`sdk`**: Claude Agent SDK options
- `model`, `max_turns`, `permission_mode`
- `allowed_tools`: List of tools agent can use
- `env`: Environment variables for managed providers

**`agent`**: Agent behavior
- `system_prompt`: Instructions prepended to every conversation

**`storage`**: File upload settings
- `upload_root`: Base directory for uploaded files (default: `uploads/`)
- `pending_dir_name`: Temporary directory for unfinalized sessions

**`api`**: API response behavior
- `return_steps`: Include execution steps in response
- `final_answer_text_policy`: `full` or `last_assistant_turn`
- `file_prompt_template`: How to mention uploaded files in prompt

**`langfuse`**: Observability settings
- `enabled`: Turn tracing on/off
- `public_key`, `secret_key`, `host`: LangFuse credentials

Environment variables override config file (e.g., `LANGFUSE_PUBLIC_KEY`).

## Custom Skills

This project includes JMI-specific skills for insurance claim processing:

**`jmi-intake-call-checkout`**
- Verifies FNOL (First Notice of Loss) intake calls
- 4-point verification: policy number, name/phone, plate/model, accident date in period
- Assesses emergency status and surveyor dispatch using weighted scoring
- Output: Structured JSON (see `.claude/skills/jmi-intake-call-checkout/references/output-schema.md`)

**`jmi-fresh-claim-doc-check`**
- Validates fresh claim submitted documents against 7-category checklist
- Cross-validates data between documents and policy
- OCR tolerance handling for 1-2 character differences (see `references/ocr-tolerance.md`)
- Uses `image-by-intent` skill for vision-based document extraction
- Output: Structured JSON (see `.claude/skills/jmi-fresh-claim-doc-check/references/output-schema.md`)

**`document-ocr-ai`**
- OCR service for extracting text from images and PDFs
- Supports KTB form templates and custom extraction

**`image-by-intent`**
- Vision-based content extraction from images/PDFs
- Intent-driven prompting for targeted information retrieval

## Testing Structure

Test files mirror the source structure:

- `tests/test_routes.py`: API endpoint tests
- `tests/test_final_answer_policy.py`: Policy behavior tests
- `tests/test_content_store.py`: Storage layer tests
- `tests/test_jmi_*_parse.py`: Insurance output parsing tests
- `tests/test_vertex_config.py`: Vertex AI configuration tests

Test data for insurance workflows:
- `tests/jmi-intake-call-checkout/cases/`: Sample intake calls + policies
- `tests/jmi-fresh-claim-doc-check/cases/`: Sample claim documents + policies

Integration test scripts:
- `tests/script/demo_single_turn.py`: Single query example
- `tests/script/demo_multi_turn.py`: Multi-turn conversation example
- `tests/script/demo_chat_client.py`: Interactive client example

## Important Patterns

### Session ID Handling

Never generate custom session IDs. Always extract from SDK messages:

```python
# ❌ Wrong
session_id = f"sess_{uuid.uuid4()}"

# ✅ Correct
async for message in query(prompt, options):
    if hasattr(message, "session_id"):
        session_id = message.session_id
```

### File Prompt Augmentation

When files are uploaded, the service automatically prepends a file list to the prompt using `api.file_prompt_template`. This guides the agent to use the `Read` tool.

### Error Handling for CLI Exit Codes

The SDK may raise exceptions for non-zero CLI exit codes even after receiving a `ResultMessage`. The executor catches this pattern:

```python
if got_result and _looks_like_cli_exit_error(exc):
    logger.warning("CLI non-zero exit but got ResultMessage, ignoring: %s", exc)
```

### Structured Output with Multiple Turns

When using `output_format` (structured outputs), set `final_answer_text_policy: last_assistant_turn` to avoid including intermediate reasoning in the final answer. The structured JSON is in the `structured_output` field.

## Documentation

Key docs in `docs/`:
- `QUICK_START.md`: Getting started guide
- `API_REFERENCE.md`: API endpoint documentation
- `VERTEX_AI_SETUP.md`: Vertex AI configuration
- `设计方案.md`: Original design document (Chinese)
- `langfuse-integration.md`: LangFuse tracing setup
- `storage-optimization.md`: Content-addressed storage design

## Common Workflows

### Adding a New Tool to Agent

Edit `conf/config.yaml`:
```yaml
sdk:
  allowed_tools:
    - Read
    - Write
    - YourNewTool  # Add here
```

Restart service. Agent can now use the tool.

### Creating a New Structured Output Profile

1. Define Pydantic model in `src/api/` (e.g., `your_profile_output.py`)
2. Add parser function and constant (e.g., `STRUCTURED_OUTPUT_PROFILE_YOUR_PROFILE`)
3. Register in `src/api/routes.py`: add to `ALLOWED_STRUCTURED_OUTPUT_PROFILES`
4. Add to `src/agent/schema_registry.py`: map profile name → Pydantic schema
5. Test with: `-F "structured_output_profile=your_profile"`

### Debugging Agent Execution

1. Enable step logging: `api.return_steps: true` in config
2. Check response `steps` array for message flow
3. Enable LangFuse: `langfuse.enabled: true`, view traces at your LangFuse host
4. Add breakpoints in `src/agent/executor.py:execute_agent_message`

### Switching Providers

Edit `conf/config.yaml` `sdk.env` section:
- Vertex AI: Set `CLAUDE_CODE_USE_VERTEX: "1"` + GCP credentials
- Bedrock: Set `CLAUDE_CODE_USE_BEDROCK: "1"` + AWS credentials
- Local: Comment out or remove `env` section

Verify with: `curl http://localhost:8000/config | jq .provider`
