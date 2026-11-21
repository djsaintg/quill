#!/usr/bin/env python3
"""A stand-in for `claude` in stream-json mode, for Quill's tests. No network, no AI.

It logs its arguments and every line Quill sends to $FAKE_LOG, then answers:
  a control request  -> success
  a user message     -> a short reply; "fail" in it -> a step that fails first;
                        "slow" -> waits a moment first (so Quill looks busy)
"""
import json
import os
import sys
import time

log = open(os.environ["FAKE_LOG"], "a")
log.write(json.dumps({"argv": sys.argv[1:]}) + "\n")
log.flush()


def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


out({"type": "system", "subtype": "init", "model": "fake-model", "session_id": "fake-session"})
for line in sys.stdin:
    log.write(line)
    log.flush()
    msg = json.loads(line)
    if msg["type"] == "control_request":
        out({"type": "control_response", "response": {"subtype": "success",
                                                      "request_id": msg["request_id"], "response": {}}})
        if msg["request"].get("subtype") == "interrupt":
            out({"type": "result", "subtype": "error_during_execution", "is_error": True})
        continue
    if msg["type"] != "user":
        continue
    text = msg["message"]["content"]
    if "slow" in text:
        time.sleep(1.5)
    if "fail" in text:
        out({"type": "assistant", "message": {"id": "m0", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "false"}}]}})
        out({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "exit 1"}]}})
        time.sleep(0.5)
    reply = "Wrapped up: docs updated." if "wrap up" in text else f"echo: {text[-40:]}"
    out({"type": "assistant", "message": {"id": f"m{time.time()}",
                                          "content": [{"type": "text", "text": reply}]}})
    out({"type": "result", "subtype": "success", "result": reply})
