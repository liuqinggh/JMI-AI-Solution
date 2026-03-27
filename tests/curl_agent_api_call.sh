curl -sS -X POST "http://127.0.0.1:8000/v1/agent/messages" \
  -F 'prompt=使用 jmi-intake-call-checkout 技能，根据附件中的通话记录与保单做四项核对并输出结构化 JSON。' \
  -F 'files=@tests/jmi-intake-call-checkout/cases/fnol-0001-6805-03399/input/Claim-Inteview-Simulation.md;type=text/markdown' \
  -F 'files=@tests/jmi-intake-call-checkout/cases/fnol-0001-6805-03399/input/policy.md;type=text/markdown' \
  -F "structured_output_profile=jmi_intake_call_checkout"