"""Run an authorized GSE implementation task through the ordinary Responses API.

This uses documented API function calling, not the Codex CLI or its login.
Complete responses, tool inputs/outputs and usage are retained as audit records.
"""

import fcntl
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOTES = Path(__file__).resolve().parent
OWNED = "/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/owned-run"
TOOLS = [
    {
        "type": "function",
        "name": "run_command",
        "strict": True,
        "description": (
            "Run a local command for the assigned implementation, returning complete output "
            "or a saved whole-output artifact. Read whole coherent units, never grep/rg or snippets. "
            "Credentials, billing, external model clients and other edit scopes are forbidden. "
            "The controller may invoke the existing LOCAL GSE/Ollama typed semantic transport."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 10800},
            },
            "required": ["command", "cwd", "timeout_seconds"],
        },
    },
    {
        "type": "function",
        "name": "apply_patch",
        "strict": True,
        "description": "Apply an *** Begin Patch formatted edit to owned project files after tracing their consumers.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"patch": {"type": "string"}},
            "required": ["patch"],
        },
    },
]


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def api_response(request, role, number):
    """Back off only explicitly rejected TPM requests; never retry uncertain calls."""
    for attempt in range(1, 5):
        with (NOTES / "ssl-responses-request.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            budget_file = NOTES / "ssl-responses-continuation-budget.json"
            if budget_file.exists():
                budget = json.loads(budget_file.read_text())
                reservations_file = NOTES / "ssl-responses-budget-reservations.json"
                reservations = json.loads(reservations_file.read_text()) if reservations_file.exists() else {}
                reservations = {
                    key: value for key, value in reservations.items() if not (NOTES / value["response_file"]).exists()
                }
                charged = 0.0
                calls = 0
                for response_file in NOTES.glob("ssl-responses-*-response.json"):
                    if response_file.stat().st_mtime < budget["started_epoch"]:
                        continue
                    response_data = json.loads(response_file.read_text())
                    usage = response_data.get("usage") or {}
                    total_input = usage.get("input_tokens", 0)
                    cached = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
                    multiplier = 2 if total_input > 272000 else 1
                    charged += (
                        max(0, total_input - cached) * 5.0 * multiplier
                        + cached * 0.1 * multiplier
                        + usage.get("output_tokens", 0) * (15.0 if multiplier == 2 else 10.0)
                    ) / 1_000_000
                    calls += 1
                # Reserve the complete model maximum at the highest Standard cache-write
                # rate. Count cache writes conservatively; this is not a billing receipt.
                reserve = (922000 * 10.0 + 32768 * 15.0) / 1_000_000
                outstanding = sum(item["usd"] for item in reservations.values())
                measurement = {
                    "format": "GSE.api-continuation-budget/1",
                    "at_utc": datetime.now(timezone.utc).isoformat(),
                    "completed_calls": calls,
                    "conservative_charge_usd": charged,
                    "outstanding_reservations_usd": outstanding,
                    "next_request_reserve_usd": reserve,
                    "limit_usd": budget["limit_usd"],
                    "source": budget["pricing_source"],
                    "is_account_balance": False,
                }
                (NOTES / "ssl-responses-continuation-cost.json").write_text(json.dumps(measurement, indent=2))
                if charged + outstanding + reserve > budget["limit_usd"]:
                    return {"api_failure": {"code": "LOCAL_AUTHORIZED_BUDGET_REACHED", **measurement}}
                reservations[f"{role}:{number}"] = {
                    "usd": reserve,
                    "response_file": f"ssl-responses-{role}-{number:03d}-response.json",
                }
                reservations_file.write_text(json.dumps(reservations, indent=2))
            try:
                with urllib.request.urlopen(request, timeout=1800) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                detail = json.loads(error.read().decode())
                save(
                    NOTES / f"ssl-responses-{role}-{number:03d}-attempt-{attempt}-http-error.json",
                    {"status": error.code, "error": detail},
                )
                if error.code == 429 and budget_file.exists():
                    reservations.pop(f"{role}:{number}", None)
                    reservations_file.write_text(json.dumps(reservations, indent=2))
                if error.code != 429 or detail.get("error", {}).get("code") != "rate_limit_exceeded" or attempt == 4:
                    return {"api_failure": {"http_status": error.code, "error": detail}}
                delay = min(60, max(2, float(error.headers.get("Retry-After", "30")) + 0.25))
                time.sleep(delay)


def run_tool(role, number, item):
    args = json.loads(item["arguments"])
    save(NOTES / f"ssl-responses-{role}-{number:03d}-{item['call_id']}-input.json", args)
    if item["name"] == "run_command":
        command, cwd, wall = args["command"], Path(args["cwd"]).resolve(), args["timeout_seconds"]
        if not cwd.is_dir() or not 1 <= wall <= 10800:
            return {"code": "INVALID_COMMAND_LOCATION_OR_WALL"}
        invocation = [
            OWNED,
            "--label",
            f"gse-ssl-api-{role}-tool",
            "--timeout",
            str(wall),
            "--",
            "/bin/zsh",
            "-c",
            command,
        ]
        incoming = None
    elif item["name"] == "apply_patch":
        executable = shutil.which("apply_patch")
        if not executable:
            return {"code": "APPLY_PATCH_UNAVAILABLE"}
        invocation, incoming, cwd, wall = [executable], args["patch"], ROOT, 120
    else:
        return {"code": "UNKNOWN_IMPLEMENTATION_TOOL"}
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY"}
    }
    start = time.monotonic()
    try:
        result = subprocess.run(
            invocation,
            input=incoming,
            text=True,
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=wall + 30,
        )
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        code = "TIMEOUT"
    logfile = NOTES / f"ssl-responses-{role}-{number:03d}-{item['call_id']}.log"
    logfile.write_text(output)
    return {
        "code": "COMMAND_COMPLETED" if code != "TIMEOUT" else "COMMAND_TIMED_OUT",
        "exit_code": code,
        "elapsed_seconds": time.monotonic() - start,
        "complete_output_path": str(logfile),
        "output_characters": len(output),
        **({"output": output} if len(output) <= 120000 else {"output_delivery": "SAVED_READ_A_COMPLETE_COHERENT_UNIT"}),
    }


def main(role, *, resume=False):
    if role not in {"controller", "runtime", "coverage"}:
        raise SystemExit("INVALID_WORKER_ROLE")
    status_path = NOTES / f"ssl-responses-{role}-status.json"
    if status_path.exists() and not resume:
        raise SystemExit("WORKER_ALREADY_RECORDED_RESUME_FROM_SAVED_RESPONSE")
    reader = runpy.run_path("/Users/rohanvinaik/Projects/SquishOS/ops/agents/bin/anthropic-consult")["read_key"]
    reader.__globals__["VARIABLE"] = "OPENAI_API_KEY"
    key, source = reader()
    instructions = (
        "You are a GSE implementation worker running through the ordinary OpenAI Responses API. "
        "Your tools execute on the authorized local project. No Codex CLI is running. "
        "No MCP servers are loaded; use full-unit AST/reference tracing instead of claiming Serena was used. "
        "Do not call external model APIs, modify billing, read secrets, or touch the API launcher. "
        "The controller IS AUTHORIZED to run the existing LOCAL GSE/Ollama typed semantic transport "
        "for its bounded checkpoint questions and audits; this is not a forbidden external model call. "
        "Use the two supplied local tools to READ, IMPLEMENT and TEST the task, not merely describe it. "
        "The run_command output is complete when included; a larger output is saved without truncation. "
        "Use exact role scopes in the handoff. Final factual results retain their requested filenames. "
        "Your peer's completion receipt is the synchronization boundary before the controller freezes source pins. "
        "Read the full owner intent in the handoff; never replace it with convenient familiar architecture. "
        "You have at most four hours and 100 API turns. No commits until both scopes stop editing and gates pass."
    )
    prompt = (NOTES / f"ssl-api-{role}-prompt.md").read_text()
    pending = [{"role": "user", "content": prompt}]
    previous, started = None, time.monotonic()
    status = {
        "format": "GSE.ssl-responses-worker/1",
        "role": role,
        "route": "ORDINARY_RESPONSES_API_FUNCTION_CALLING",
        "model": "gpt-6.1-sol",
        "credential_source": source,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "state": "STARTING",
        "turns": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    first = 1
    if resume:
        status = json.loads(status_path.read_text())
        redirect = json.loads((NOTES / f"ssl-responses-{role}-redirect.json").read_text())
        payload = json.loads(Path(redirect["last_response_file"]).read_text())
        if payload["id"] != redirect["response_id"] or status["response_id"] != payload["id"]:
            raise SystemExit("RESUME_RESPONSE_IDENTITY_CHANGED")
        previous, first = payload["id"], status["turns"] + 1
        pending = []
        for item in payload.get("output", []):
            if item.get("type") == "function_call":
                result_path = NOTES / f"ssl-responses-{role}-{first - 1:03d}-{item['call_id']}-output.json"
                if not result_path.is_file():
                    raise SystemExit("RESUME_TOOL_OUTCOME_UNRECORDED_DO_NOT_REPEAT")
                pending.append(
                    {"type": "function_call_output", "call_id": item["call_id"], "output": result_path.read_text()}
                )
        status.update(state="RESUMING_FOR_USER_CHECKPOINT_PRIORITY", resumed_at=datetime.now(timezone.utc).isoformat())
        for field in ("http_status", "error", "ended_at"):
            status.pop(field, None)
    status_path.write_text(json.dumps(status, indent=2))
    for number in range(first, first + (35 if role == "coverage" else 100)):
        steering_path = NOTES / f"ssl-responses-{role}-steering.json"
        if steering_path.is_file():
            steering = steering_path.read_bytes()
            steering_hash = hashlib.sha256(steering).hexdigest()
            if status.get("steering_sha256") != steering_hash:
                pending.append({"role": "user", "content": json.dumps(json.loads(steering))})
                status["steering_sha256"] = steering_hash
                status_path.write_text(json.dumps(status, indent=2))
        if time.monotonic() - started >= 14400:
            status["state"] = "WALL_BUDGET_REACHED"
            break
        body = {
            "model": "gpt-6.1-sol",
            "service_tier": "default",
            "reasoning": {"effort": "high"},
            "instructions": instructions,
            "input": pending,
            "tools": TOOLS,
            "max_output_tokens": 32768,
            "parallel_tool_calls": False,
            "context_management": [{"type": "compaction", "compact_threshold": 120000}],
            "store": True,
        }
        if previous:
            body["previous_response_id"] = previous
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "User-Agent": "GSE-Implementation-API/1",
            },
        )
        try:
            payload = api_response(request, role, number)
        except (urllib.error.URLError, TimeoutError) as error:
            status.update(state="TRANSPORT_INTERRUPTED_NO_RETRY", error=str(error))
            break
        if "api_failure" in payload:
            status.update(state="API_REJECTED", **payload["api_failure"])
            break
        save(NOTES / f"ssl-responses-{role}-{number:03d}-response.json", payload)
        previous = payload["id"]
        usage = payload.get("usage") or {}
        status.update(state="RUNNING", turns=number, response_id=previous)
        for field in ("input_tokens", "output_tokens"):
            status[field] += usage.get(field, 0)
        status_path.write_text(json.dumps(status, indent=2))
        print(json.dumps(status), flush=True)
        if payload.get("status") != "completed":
            status.update(state="API_RESPONSE_INCOMPLETE", incomplete_details=payload.get("incomplete_details"))
            break
        calls = [row for row in payload.get("output", []) if row.get("type") == "function_call"]
        if not calls:
            text = "\n".join(
                block.get("text", "")
                for row in payload.get("output", [])
                if row.get("type") == "message"
                for block in row.get("content", [])
                if block.get("type") == "output_text"
            )
            (NOTES / f"ssl-responses-{role}-last-message.md").write_text(text)
            status["state"] = "FINISHED"
            break
        pending = []
        for item in calls:
            result = run_tool(role, number, item)
            save(NOTES / f"ssl-responses-{role}-{number:03d}-{item['call_id']}-output.json", result)
            pending.append({"type": "function_call_output", "call_id": item["call_id"], "output": json.dumps(result)})
    else:
        status["state"] = "API_TURN_BUDGET_REACHED"
    status["ended_at"] = datetime.now(timezone.utc).isoformat()
    status_path.write_text(json.dumps(status, indent=2))
    print(json.dumps(status), flush=True)
    return 0 if status["state"] == "FINISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], resume="--resume" in sys.argv[2:]))
