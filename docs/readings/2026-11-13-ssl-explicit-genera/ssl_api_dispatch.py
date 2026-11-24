"""Run the authorized SSL implementation workers through key-based Codex API access.

The key is read using SquishOS's existing Anthropic-store reader with the
OpenAI variable selected. It is never serialized or sent in a prompt. Codex's
custom provider consumes it from the process environment; generated shell
commands exclude that variable. The ChatGPT login remains untouched.
"""

import json
import os
import runpy
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[3]
    notes = Path(__file__).resolve().parent
    intent = notes / "ssl-api-dispatch-intent.json"
    if intent.exists():
        raise SystemExit("DISPATCH_ALREADY_RECORDED_USE_EXISTING_WORKER_SESSIONS")
    reader = runpy.run_path("/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/anthropic-consult")["read_key"]
    reader.__globals__["VARIABLE"] = "OPENAI_API_KEY"
    key, source = reader()
    environment = dict(os.environ)
    environment["OPENAI_API_KEY"] = key
    environment["CODEX_HOME"] = str(Path.home() / ".config/codex-build/home")
    provider = (
        'model_providers.gse_api={name="OpenAI API",'
        'base_url="https://api.openai.com/v1",env_key="OPENAI_API_KEY",'
        'wire_api="responses",requires_openai_auth=false,'
        "request_max_retries=0,stream_max_retries=0}"
    )
    base = [
        "/opt/homebrew/Caskroom/codex/0.166.0/bin/codex",
        "exec",
        "--ignore-user-config",
        "--cd",
        str(root),
        "--model",
        "gpt-6.1-sol",
        "--sandbox",
        "danger-full-access",
        "--json",
        "--color",
        "never",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="high"',
        "-c",
        'model_provider="gse_api"',
        "-c",
        provider,
        "-c",
        'shell_environment_policy.exclude=["OPENAI_API_KEY","CODEX_API_KEY"]',
    ]
    for feature in (
        "apps",
        "plugins",
        "browser_use",
        "browser_use_external",
        "computer_use",
        "image_generation",
        "multi_agent",
        "skill_search",
        "tool_suggest",
        "in_app_browser",
        "goals",
    ):
        base.extend(["--disable", feature])
    receipt = {
        "format": "GSE.ssl-api-dispatch/1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "credential_source": source,
        "authentication": "OPENAI_API_KEY_CUSTOM_RESPONSES_PROVIDER",
        "chatgpt_login_modified": False,
        "model": "gpt-6.1-sol",
        "effort": "high",
        "workers": {},
    }
    with intent.open("x") as stream:
        json.dump(receipt, stream, indent=2)
    workers = []
    for role in ("controller", "runtime"):
        prompt = notes / f"ssl-api-{role}-prompt.md"
        log = notes / f"ssl-api-{role}-events.jsonl"
        final = notes / f"ssl-api-{role}-last-message.md"
        with prompt.open() as incoming:
            outgoing = log.open("x")
            try:
                process = subprocess.Popen(
                    [*base, "--output-last-message", str(final), "-"],
                    stdin=incoming,
                    stdout=outgoing,
                    stderr=subprocess.STDOUT,
                    cwd=root,
                    env=environment,
                )
            finally:
                outgoing.close()
        receipt["workers"][role] = {
            "pid": process.pid,
            "prompt": str(prompt),
            "events": str(log),
            "last_message": str(final),
            "status": "RUNNING",
        }
        workers.append((role, process))
    state = notes / "ssl-api-dispatch-status.json"
    state.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    while any(process.poll() is None for _, process in workers):
        changed = False
        for role, process in workers:
            code = process.poll()
            record = receipt["workers"][role]
            if code is not None and record["status"] == "RUNNING":
                record.update(status="FINISHED", exit_code=code)
                changed = True
        if changed:
            state.write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps(receipt), flush=True)
        time.sleep(2)
    for role, process in workers:
        receipt["workers"][role].update(status="FINISHED", exit_code=process.returncode)
    receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
    state.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return max(process.returncode != 0 for _, process in workers)


if __name__ == "__main__":
    raise SystemExit(main())
