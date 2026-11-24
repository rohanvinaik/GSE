"""Replay exact checkpoint packets through the ordinary sustained typed writer.

This helper makes no model/service calls. In particular, it never relabels a
98K-context answer as an earlier 65K-context answer, and never rebinds a reply
to a new post-revision question. Native sources, joint constraints and admission
remain the ordinary builder's responsibility. This is not an activation tool.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from GSE.curation.lexicon_builder.completion import complete_dictionary
from GSE.curation.lexicon_builder.epoch import fingerprint, read, record
from GSE.curation.lexicon_builder.residual import OllamaTransport, _request_id

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "data/lexicon_builder/2026-11-12/ssl-explicit-genera/ssl-api-checkpoint"


class PacketTransport:
    """An exact retained wire packet under its actual pinned protocol identity."""

    def __init__(self, packet_path, answers_path, configuration):
        self.packet_path = Path(packet_path)
        self.answers_path = Path(answers_path)
        self.packet = read(self.packet_path)
        answers = read(self.answers_path)
        config = configuration["configuration"]
        # Construction computes the current protocol digest locally; pin() and
        # __call__ are deliberately never invoked on this service transport.
        local = OllamaTransport(
            config["model"],
            timeout=config["timeout_seconds"],
            context_tokens=config["context_tokens"],
            thinking=config["thinking"],
            output_tokens=config["output_tokens"],
        )
        artifact = config["artifact"]
        expected = f"{config['model']}#{artifact['digest']}@{local._protocol_digest}"
        if artifact["model"] != config["model"] or config["identity"] != expected:
            raise ValueError("CHECKPOINT_PACKET_PROTOCOL_IDENTITY_CHANGED")
        self.identity = expected
        if (
            answers.keys() != {"format", "questions_sha256", "transport", "answers"}
            or answers["format"] != "GSE.ssl-checkpoint-local-answers/1"
            or answers["questions_sha256"] != fingerprint(self.packet_path)
            or answers["transport"] != self.identity
            or type(answers["answers"]) is not list
            or self.packet.get("format") != "GSE.ssl-checkpoint-local-questions/1"
        ):
            raise ValueError("CHECKPOINT_PACKET_ANSWERS_IDENTITY_CHANGED")
        self.requests, self.answers = {}, {}
        coordinates = []
        for row in self.packet["questions"]:
            identity = row["request_id"]
            if (
                row.keys() != {"request_id", "request", "schema"}
                or identity != _request_id(row["request"])
                or identity in self.requests
            ):
                raise ValueError("CHECKPOINT_PACKET_QUESTION_IDENTITY_CHANGED")
            self.requests[identity] = row
            coordinates.append([row["request"]["entry_id"], row["request"]["bank"]])
        if coordinates != self.packet["coordinates"] or len({tuple(pair) for pair in coordinates}) != len(coordinates):
            raise ValueError("CHECKPOINT_PACKET_COORDINATES_CHANGED")
        for row in answers["answers"]:
            if (
                type(row) is not dict
                or row.keys() != {"request_id", "raw_output"}
                or row["request_id"] not in self.requests
                or row["request_id"] in self.answers
                or type(row["raw_output"]) is not str
            ):
                raise ValueError("CHECKPOINT_PACKET_REPLY_IDENTITY_CHANGED")
            self.answers[row["request_id"]] = row["raw_output"]
        self.replayed = []

    def check(self, payload, schema):
        identity = _request_id(payload)
        original = self.requests.get(identity)
        if original is None or original["request"] != payload or original["schema"] != schema:
            raise ValueError("CHECKPOINT_PACKET_FRESH_QUESTION_CHANGED")
        if identity not in self.answers:
            raise ValueError("CHECKPOINT_PACKET_EXACT_REPLY_MISSING")
        return identity

    def __call__(self, payload, schema):
        identity = self.check(payload, schema)
        self.replayed.append(identity)
        return self.answers[identity]


class PacketSet:
    """Dispatch independent packets without merging different model identities."""

    def __init__(self, transports):
        if not transports or len({transport.identity for transport in transports}) != 1:
            raise ValueError("CHECKPOINT_PACKET_MIXED_TRANSPORT_IDENTITIES")
        self.identity = transports[0].identity
        self.transports = tuple(transports)
        self.by_id = {}
        for transport in transports:
            for identity in transport.requests:
                if identity in self.by_id:
                    raise ValueError("CHECKPOINT_PACKET_DUPLICATE_QUESTION")
                self.by_id[identity] = transport

    def check(self, payload, schema):
        transport = self.by_id.get(_request_id(payload))
        if transport is None:
            raise ValueError("CHECKPOINT_PACKET_FRESH_QUESTION_CHANGED")
        return transport.check(payload, schema)

    def __call__(self, payload, schema):
        self.check(payload, schema)
        return self.by_id[_request_id(payload)](payload, schema)


def write_packets(database, transports, coordinates, report, *, rule_version):
    """One full version-boundary preflight, then bounded exact entry-bank work."""
    database = Path(database).resolve()
    if database.parent != WORK or database.name not in {"teaching.db", "checkpoint-teaching.db", "candidate.db"}:
        raise ValueError("CHECKPOINT_PACKET_REQUIRES_OWNED_PRIVATE_DATABASE")
    coordinates = tuple(tuple(pair) for pair in coordinates)
    if not coordinates or len(set(coordinates)) != len(coordinates):
        raise ValueError("CHECKPOINT_PACKET_INVALID_SELECTED_COORDINATES")
    model = PacketSet(transports)
    by_coordinate = {}
    for transport in transports:
        for row in transport.requests.values():
            pair = (row["request"]["entry_id"], row["request"]["bank"])
            if pair in by_coordinate:
                raise ValueError("CHECKPOINT_PACKET_DUPLICATE_COORDINATE")
            by_coordinate[pair] = {"rule_version": rule_version, **row}
    if not set(coordinates) <= set(by_coordinate):
        raise ValueError("CHECKPOINT_PACKET_SELECTED_QUESTION_MISSING")
    # The ordinary writer reconstructs each complete original request using
    # verified rule history and fresh native source evidence. Changed scopes
    # are rejected, not silently rebased. Accepted requests resume via their
    # ordinary atomic receipts without another transport invocation.
    before = fingerprint(database)
    result = complete_dictionary(
        database,
        model,
        len(coordinates),
        entry_bank_questions=coordinates,
        historical_questions={pair: by_coordinate[pair] for pair in coordinates},
        continue_cohorts=True,
        max_calls_per_entry=1,
        max_entries_per_pass=len(coordinates),
        priority="zipf",
        progress=lambda row: print(json.dumps(row), flush=True),
    )
    receipt = {
        "format": "GSE.checkpoint-retained-packet-writer/1",
        "database": str(database),
        "before_sha256": before,
        "after_sha256": fingerprint(database),
        "transport": model.identity,
        "original_rule_version": rule_version,
        "packets": [
            {
                "questions": str(transport.packet_path),
                "questions_sha256": fingerprint(transport.packet_path),
                "answers": str(transport.answers_path),
                "answers_sha256": fingerprint(transport.answers_path),
                "replayed_request_ids": transport.replayed,
            }
            for transport in transports
        ],
        "writer": result,
        "new_model_service_calls": 0,
        "postflight": "REQUIRED_BEFORE_PUBLICATION",
        "activation_performed": False,
    }
    record(Path(report), receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--configuration", required=True, type=Path)
    parser.add_argument("--packet", required=True, action="append", type=Path)
    parser.add_argument("--answers", required=True, action="append", type=Path)
    parser.add_argument("--coordinates", required=True, type=Path, help="JSON array of exact [entry_id,bank] pairs")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--rule-version", required=True, help="Exact original immutable relation version, not the new head"
    )
    args = parser.parse_args()
    if len(args.packet) != len(args.answers):
        parser.error("Each exact packet requires its own answer file")
    configuration = read(args.configuration)
    transports = [PacketTransport(packet, answers, configuration) for packet, answers in zip(args.packet, args.answers)]
    write_packets(args.database, transports, read(args.coordinates), args.report, rule_version=args.rule_version)
