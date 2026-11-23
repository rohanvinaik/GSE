"""Bounded typed CLI rulings for source-challenged BODY replies, then admission."""

import json
import os
import subprocess
import sys
import time
from importlib import import_module

from GSE.curation.lexicon_builder import epoch
from GSE.curation.lexicon_builder.model_batch import batch_contract
from GSE.curation.lexicon_builder.model_protocol import model_input, protocol_contract
from GSE.curation.lexicon_builder.residual import _canonical_json, _request_id

round_ = import_module("docs.readings.2026-11-13-ssl-explicit-genera.vertebrate_021_approved")
preview = import_module("docs.readings.2026-11-13-ssl-explicit-genera.prefetch_vertebrate_021")
NOTES, WORK = round_.NOTES, round_.WORK
PHASE = WORK / "zipf/epoch-01"
MANIFEST = NOTES / "021-approved-adjudication-manifest.json"
RESULT = NOTES / "021-approved-adjudicated-result.json"


def ruling(raw):
    value = json.loads(raw)
    if type(value) is not dict or set(value) != {"BODY"}:
        raise ValueError("ADJUDICATION_INVALID_SINGLE_BANK_OUTPUT")
    sign = value["BODY"]
    if sign is not None and (type(sign) is not int or sign not in (-1, 0, 1)):
        raise ValueError("ADJUDICATION_INVALID_TERNARY_SIGN")
    return sign


def collect_native():
    contract = epoch.read(NOTES / "021-approved-prefetch-contract.json")
    rows = []
    for index, item in enumerate(contract["requests"]):
        prefix = "teach" if index == 0 else "audit"
        path = PHASE / (prefix + "-" + item["request_id"] + ".result.json")
        if not path.exists():
            return None
        result = epoch.read(path)
        if "raw_output" not in result:
            raise ValueError("ADJUDICATION_NATIVE_TRANSPORT_DID_NOT_COMPLETE")
        intent = epoch.read(path.with_name(path.name.replace(".result.json", ".intent.json")))
        rows.append({**item, "raw_output": result["raw_output"], "transport": intent["transport"],
                     "schema": intent["schema"], "sign": ruling(result["raw_output"])})
    return rows


def cli_questions(native):
    challenged = [row for row in native[1:] if row["sign"] != 1]
    if native[0]["sign"] != 1 or not challenged:
        raise ValueError("ADJUDICATION_REQUIRES_REVIEWED_POSITIVE_SEED_AND_CHALLENGES")
    all_records = epoch.read(NOTES / "021-approved-source-context.json")["observations"]
    ids = {row["entry_id"] for row in challenged}
    records = [r for r in all_records if r["entry_id"] in ids]
    requests = preview.prepare_requests(round_.BASE, records)
    expected = {row["entry_id"]: row["request_id"] for row in challenged}
    if any(expected[r.entry_id] != r.request_id for r in requests):
        raise ValueError("ADJUDICATION_QUESTION_CHANGED")
    # Record the source reading before the stronger solver's answer. No prior
    # answer, expected per-case label, or proposed population rule enters its input.
    epoch.record(NOTES / "021-approved-source-adjudication.json", {
        "code": "NATIVE_MODEL_ZEROS_NOT_JUSTIFIED_UNDER_APPROVED_CONSTITUTIVE_ANATOMY",
        "request_verbatim": epoch.read(NOTES / "021-body-convention-approval.json")["request_verbatim"],
        "instrument": "Founder-approved BODY condition and source-verified exact defining-genus context",
        "specimen": [row["entry_id"] for row in challenged],
        "source_refs": ["021-body-convention-approval.json", "021-approved-source-context.json"],
        "rationale": "Each selected native noun is an ALIVE vertebrate kind with its complete defining skeletal/spinal genus witness. The approved constitutive-anatomy condition entails positive BODY. The signed native replies do not justify orthogonality.",
        "kind": "DEFINITIONAL_DERIVATION_UNDER_APPROVED_REPRESENTATIONAL_SPECIFICATION",
        "falsifier": "Wrong native sense, unverified path, non-kind reference, missing anatomical genus content, or an unmet ALIVE premise",
        "test": "Regenerate exact native context; retain full request/schema identity; bounded typed second-provider ruling; existing source/closure checks and full replay",
        "writes": False,
    })
    shared, items, schemas = None, [], {}
    for index, request in enumerate(requests):
        wire = model_input(request.payload())
        coordinate, data = wire.pop("coordinate"), wire.pop("input")
        if shared is not None and shared != wire:
            raise ValueError("ADJUDICATION_SHARED_PROTOCOL_MISMATCH")
        shared = wire
        slot = f"q{index}"
        items.append({"slot": slot, "request_id": request.request_id, "coordinate": coordinate, "input": data})
        schemas[slot] = request.output_schema()
    packet = {**batch_contract(), "shared_protocol": shared, "items": items}
    schema = {"type": "object", "properties": schemas, "required": list(schemas), "additionalProperties": False}
    prompt_path = NOTES / "021-approved-cli-bank-input.json"
    epoch.record(prompt_path, packet)
    if len(_canonical_json(packet).encode()) > 900000:
        raise ValueError("ADJUDICATION_INPUT_EXCEEDS_DECLARED_BOUND")
    env = os.environ.copy()
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                "CLAUDECODE", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(key, None)
    auth = json.loads(subprocess.check_output(["claude", "auth", "status"], env=env, text=True))
    if auth.get("authMethod") != "claude.ai" or auth.get("apiProvider") != "firstParty" or not auth.get("loggedIn"):
        raise ValueError("ADJUDICATION_SUBSCRIPTION_AUTH_NOT_VERIFIED")
    output = NOTES / "021-approved-cli-bank-result.json"
    if not output.exists():
        intent = NOTES / "021-approved-cli-bank-intent.json"
        if intent.exists():
            raise ValueError("ADJUDICATION_INTERRUPTED_ATTEMPT_NO_AUTOMATIC_RETRY")
        epoch.record(intent, {"input_sha256": epoch.fingerprint(prompt_path), "schema": schema,
                             "model": "claude-fable-5-2", "bank_questions": len(requests)})
        args = ["claude", "--safe-mode", "--print", "--model", "claude-fable-5-2", "--effort", "high",
                "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
                "--output-format", "json", "--json-schema", _canonical_json(schema),
                "--system-prompt", _canonical_json({"operation": "LEXICAL_COMPONENT_ENTAILMENT",
                    "scope": "SUPPLIED_TYPED_PACKET", "output": "REQUESTED_SCHEMA_ONLY",
                    "unresolved": "NULL_NOT_ZERO"})]
        with output.open("x") as out, (NOTES / "021-approved-cli-bank-stderr.log").open("x") as err:
            completed = subprocess.run(args, input=_canonical_json(packet), text=True, stdout=out, stderr=err, env=env)
        if completed.returncode:
            raise ValueError("ADJUDICATION_CLI_FAILED_NO_AUTOMATIC_RETRY")
    result = epoch.read(output)
    answers = result.get("structured_output")
    if result.get("is_error") or type(answers) is not dict or set(answers) != set(schemas):
        raise ValueError("ADJUDICATION_CLI_STRUCTURED_OUTPUT_NOT_COMPLETE")
    cli_version = subprocess.check_output(["claude", "--version"], env=env, text=True).strip()
    identity = "claude-code-subscription:claude-fable-5-2@" + _request_id({"cli_version": cli_version, "protocol": protocol_contract(), "schema": schema})
    corrections = {}
    for index, request in enumerate(requests):
        raw = _canonical_json(answers[f"q{index}"])
        ruling(raw)
        corrections[request.request_id] = {"entry_id": request.entry_id, "raw_output": raw, "transport": identity}
    epoch.record(NOTES / "021-approved-cli-bank-metadata.json", {
        "route": "CLAUDE_CODE_SUBSCRIPTION_CLI_TYPED_BANK_WRITER", "auth_method": auth["authMethod"],
        "api_key_source": "none", "declared_remote_model": "claude-fable-5-2", "remote_weight_digest": "NOT_AVAILABLE",
        "cli_version": cli_version, "bank_questions": len(requests), "transport_invocations": 1,
        "tools": [], "mcp_servers": [], "input_sha256": epoch.fingerprint(prompt_path),
        "stop_reason": result.get("stop_reason"), "num_turns": result.get("num_turns"),
        "usage": result.get("usage"), "model_usage": result.get("modelUsage"),
        "list_price_equivalent_usd": result.get("total_cost_usd"),
        "billing_note": "Subscription CLI; list-price equivalent is not an API-credit debit.",
    })
    manifest = {"format": "gse.source-adjudicated-bank-rulings/1", "native_questions": native,
                "corrections": corrections, "unique_bank_questions": len(native),
                "actual_bank_questions": len(native) + len(corrections), "transport_invocations": len(native) + 1,
                "source_review": "021-approved-source-adjudication.json", "protocol": protocol_contract()["format"],
                "cli_input_sha256": epoch.fingerprint(prompt_path), "cli_result_sha256": epoch.fingerprint(output)}
    epoch.record(MANIFEST, manifest)
    print("BOUNDED_BODY_ADJUDICATIONS_RECORDED", {row["entry_id"]: ruling(row["raw_output"]) for row in corrections.values()}, flush=True)
    return manifest


class RulingReplay:
    """Consume exact archived provider rulings; never invent an assignment."""

    def __init__(self, manifest):
        native, corrections = manifest["native_questions"], manifest["corrections"]
        indexed = {r["request_id"]: r for r in native}
        if (
            manifest["format"] != "gse.source-adjudicated-bank-rulings/1"
            or len(native) != 5 or len(indexed) != len(native)
            or manifest["unique_bank_questions"] != len(native)
            or manifest["actual_bank_questions"] != len(native) + len(corrections)
            or set(corrections) != {r["request_id"] for r in native[1:] if ruling(r["raw_output"]) != 1}
        ):
            raise ValueError("ADJUDICATION_MANIFEST_ACCOUNTING_MISMATCH")
        for request_id, row in corrections.items():
            if row["entry_id"] != indexed[request_id]["entry_id"] or not row["transport"]:
                raise ValueError("ADJUDICATION_CORRECTION_IDENTITY_MISMATCH")
            ruling(row["raw_output"])
        self.manifest = manifest
        self.identity = "source-reviewed-ruling-replay@" + _request_id(manifest)

    def __call__(self, payload, schema):
        request_id = _request_id(payload)
        native = next((r for r in self.manifest["native_questions"] if r["request_id"] == request_id), None)
        if native is None or schema != native["schema"] or payload.get("entry_id") != native["entry_id"]:
            raise ValueError("ADJUDICATION_REPLAY_QUESTION_OR_SCHEMA_MISMATCH")
        chosen = self.manifest["corrections"].get(request_id, native)
        return chosen["raw_output"]


def validate_manifest_artifacts():
    manifest = epoch.read(MANIFEST)
    RulingReplay(manifest)
    if collect_native() != manifest["native_questions"]:
        raise ValueError("ADJUDICATION_NATIVE_SOURCE_JOURNALS_CHANGED")
    if (
        epoch.fingerprint(NOTES / "021-approved-cli-bank-input.json") != manifest["cli_input_sha256"]
        or epoch.fingerprint(NOTES / "021-approved-cli-bank-result.json") != manifest["cli_result_sha256"]
    ):
        raise ValueError("ADJUDICATION_CLI_ARTIFACT_CHANGED")
    packet = epoch.read(NOTES / "021-approved-cli-bank-input.json")
    result = epoch.read(NOTES / "021-approved-cli-bank-result.json")
    intent = epoch.read(NOTES / "021-approved-cli-bank-intent.json")
    metadata = epoch.read(NOTES / "021-approved-cli-bank-metadata.json")
    identity = "claude-code-subscription:claude-fable-5-2@" + _request_id({
        "cli_version": metadata["cli_version"], "protocol": protocol_contract(), "schema": intent["schema"],
    })
    if metadata["auth_method"] != "claude.ai" or metadata["api_key_source"] != "none":
        raise ValueError("ADJUDICATION_PROVIDER_ROUTE_CHANGED")
    if len(packet["items"]) != len(manifest["corrections"]):
        raise ValueError("ADJUDICATION_SLOT_COUNT_MISMATCH")
    for item in packet["items"]:
        chosen = manifest["corrections"][item["request_id"]]
        if chosen["raw_output"] != _canonical_json(result["structured_output"][item["slot"]]) or chosen["transport"] != identity:
            raise ValueError("ADJUDICATION_PROVIDER_RULING_MISMATCH")
    return manifest


def run():
    round_.verify_sources()
    while (native := collect_native()) is None:
        time.sleep(10)
    manifest = epoch.read(MANIFEST) if MANIFEST.exists() else cli_questions(native)
    validate_manifest_artifacts()
    # The original controller completes its own unchanged audit history and
    # full replay first. Its original result is never replaced.
    original_path = WORK / "zipf/arm-result.json"
    while not original_path.exists() or not (NOTES / "021-approved-notebook-update.json").exists():
        status = epoch.read(NOTES / "021-approved-round-status.json")
        if status["code"] in {"APPROVED_BODY_CYCLE_STOPPED", "APPROVED_BODY_FINALIZATION_STOPPED"}:
            raise ValueError("ADJUDICATION_ORIGINAL_CYCLE_STOPPED:" + status["reason"])
        time.sleep(10)
    original = epoch.read(original_path)
    if original["epochs"][0]["code"] != "RULE_WITHHELD_INDEPENDENT_AUDIT" or original["replay"]["code"] != "REPLAY_VALIDATED":
        raise ValueError("ADJUDICATION_REQUIRES_ORIGINAL_SOURCE_CHALLENGE_AND_FULL_REPLAY")
    if any(ruling(row["raw_output"]) != 1 for row in manifest["corrections"].values()):
        round_.status("BODY_ADJUDICATION_REMAINS_UNRESOLVED", model_bank_questions=manifest["actual_bank_questions"])
        return
    round_.status("APPLYING_SOURCE_ADJUDICATED_BODY_RULE", model_bank_questions=manifest["actual_bank_questions"])
    raw = epoch.read(PHASE / "reviewed-input.json")
    phase = WORK / "adjudicated"
    phase.mkdir(exist_ok=True)
    transport = RulingReplay(manifest)
    audited_path = phase / "audit.json"
    audited = epoch.read(audited_path) if audited_path.exists() else epoch.run_workflow_input(raw, transport, max_calls=4)
    epoch.record(audited_path, audited)
    [candidate] = audited["candidates"]
    if candidate["audit_outcomes"] != {"MODEL_AGREEMENT": 4} or any(r["code"] != "STAGED_ONLY" for r in candidate["staging"]):
        raise ValueError("ADJUDICATION_FAILED_EXISTING_AUDIT_GATE")
    family = next(iter(epoch.parse_plan(epoch.read(NOTES / "021-approved-coherence-plan.json")).values()))
    output = phase / "candidate.db"
    migration = epoch.admit_and_migrate(PHASE / "teaching.db", output, phase, raw, audited, family, epoch.read(PHASE / "staged.json"))
    count, changes = epoch.exact_delta(round_.BASE, output)
    candidate_sha256 = epoch.fingerprint(output)
    admitted = {**original["epochs"][0], **migration, "code": "RULE_ADMITTED", "candidate": str(output),
                "candidate_sha256": candidate_sha256, "audit_outcomes": candidate["audit_outcomes"],
                "typed_questions_used": manifest["actual_bank_questions"]}
    final = {**original, "format": "gse.lexicon-adjudicated-round/1", "candidate": str(output),
             "candidate_sha256": candidate_sha256, "definitions_compared": count, "epochs": [admitted],
             "admitted": [{"epoch": 1, "family": family.id, "rule_id": migration["rule_id"]}],
             "changes": changes, "new_cells": len(epoch.gains({"changes": changes})), "reopened_cells": 0,
             "replay": migration["replay"], "typed_questions_used": manifest["actual_bank_questions"],
             "unique_bank_questions": manifest["unique_bank_questions"], "adjudication_manifest": str(MANIFEST),
             "prior_native_result": str(original_path), "prior_native_result_sha256": epoch.fingerprint(original_path)}
    epoch.record(RESULT, final)
    subprocess.run([sys.executable, "-u", "-m", "docs.readings.2026-11-13-ssl-explicit-genera.finish_vertebrate_021",
                    "--result", str(RESULT)], cwd=round_.ROOT, check=True)


if __name__ == "__main__":
    try:
        run()
    except BaseException as error:
        epoch.record(NOTES / "021-approved-adjudication-failure.json", {"code": "TYPED_BODY_ADJUDICATION_STOPPED", "reason": repr(error)})
        raise
