#!/usr/bin/env python3
"""Prove a narrowly allowed FLOAT checksum difference against a saved SQL dump.

This is a logical SQL restore proof, not a claim of bit-identical FLOAT storage.
It never changes database contents and never includes row values in diagnostics.
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


ALLOWED_FLOAT_TABLES = frozenset({
    "acore_characters.character_homebind",
    "acore_characters.characters",
    "acore_world.gameobject",
})
SIGNATURE_KEYS = frozenset({"tables", "columns", "indexes", "counts", "checksums", "objects"})
SCHEMAS = frozenset({"acore_auth", "acore_characters", "acore_world", "acore_playerbots"})
IDENTIFIER = re.compile(r"[A-Za-z0-9_]+\Z")
INSERT = re.compile(rb"INSERT INTO `([A-Za-z0-9_]+)` VALUES[ \t]+")
USE = re.compile(rb"USE `([A-Za-z0-9_]+)`;[\r\n]*\Z")
DATA_HEADER = re.compile(rb"-- Dumping data for table `([A-Za-z0-9_]+)`[\r\n]*\Z")


class RestoreProofError(RuntimeError):
    """A data-free error safe to show to the operator."""


def _private_file(path):
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    return os.fdopen(descriptor, "wb")


def _write_evidence(path, evidence):
    with _private_file(path) as stream:
        stream.write((json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _rows(text, width, label):
    if not isinstance(text, str):
        raise RestoreProofError(f"Invalid {label} metadata type")
    rows = [line.split("\t") for line in text.splitlines()]
    if any(len(row) != width for row in rows):
        raise RestoreProofError(f"Incomplete {label} metadata")
    return rows


def _numeric_map(text, tables, label):
    result = {}
    for name, value in _rows(text, 2, label):
        if name not in tables or name in result or not value.isascii() or not value.isdigit():
            raise RestoreProofError(f"Invalid or duplicate {label} metadata")
        result[name] = int(value)
    if set(result) != set(tables):
        raise RestoreProofError(f"Incomplete {label} table coverage")
    return result


def validate_signatures(expected, restored):
    """Return checksum deltas only after all non-checksum metadata is identical."""
    if not isinstance(expected, dict) or not isinstance(restored, dict) \
            or set(expected) != SIGNATURE_KEYS or set(restored) != SIGNATURE_KEYS:
        raise RestoreProofError("Missing or unexpected signature metadata")
    if any(not isinstance(value, str) for signature in (expected, restored) for value in signature.values()):
        raise RestoreProofError("Invalid signature metadata type")
    for key in sorted(SIGNATURE_KEYS - {"checksums"}):
        if expected[key] != restored[key]:
            raise RestoreProofError(f"Restore metadata differs: {key}")
    if expected["objects"].strip():
        raise RestoreProofError("Routines/triggers/events/views need a dedicated proof")
    tables = {}
    for schema, table, engine, collation in _rows(expected["tables"], 4, "table"):
        name = f"{schema}.{table}"
        if schema not in SCHEMAS or not IDENTIFIER.fullmatch(table) or name in tables or not engine or not collation:
            raise RestoreProofError("Invalid or duplicate table metadata")
        tables[name] = []
    if {name.split(".")[0] for name in tables} != SCHEMAS:
        raise RestoreProofError("All four schemas must be represented")
    column_names = set()
    for row in _rows(expected["columns"], 9, "column"):
        schema, table, column, ordinal, kind = row[:5]
        name = f"{schema}.{table}"
        if name not in tables or not IDENTIFIER.fullmatch(column) or not ordinal.isdigit() or int(ordinal) < 1:
            raise RestoreProofError("Invalid column metadata")
        if (name, column) in column_names:
            raise RestoreProofError("Duplicate column metadata")
        column_names.add((name, column))
        tables[name].append((column, int(ordinal), kind))
    for columns in tables.values():
        if not columns or sorted(item[1] for item in columns) != list(range(1, len(columns) + 1)):
            raise RestoreProofError("Incomplete column ordinal coverage")
    index_keys = set()
    for row in _rows(expected["indexes"], 9, "index"):
        schema, table, index, non_unique, sequence = row[:5]
        name = f"{schema}.{table}"
        key = (name, index, sequence)
        if name not in tables or non_unique not in {"0", "1"} or not sequence.isdigit() or int(sequence) < 1:
            raise RestoreProofError("Invalid index metadata")
        if key in index_keys:
            raise RestoreProofError("Duplicate index metadata")
        index_keys.add(key)
    counts = _numeric_map(expected["counts"], tables, "row count")
    before = _numeric_map(expected["checksums"], tables, "original checksum")
    after = _numeric_map(restored["checksums"], tables, "restored checksum")
    differences = {name: {"original": before[name], "restored": after[name]}
                   for name in sorted(tables) if before[name] != after[name]}
    if not set(differences).issubset(ALLOWED_FLOAT_TABLES):
        raise RestoreProofError("A checksum mismatch is outside the exact FLOAT-table allowlist")
    for name in differences:
        if not any(re.match(r"float(?:\(|\Z)", kind, re.IGNORECASE) for _, _, kind in tables[name]):
            raise RestoreProofError("An allowed checksum table has no FLOAT column")
    return tables, counts, differences


def _statement_complete(statement):
    quoted = escaped = False
    for value in statement:
        if escaped:
            escaped = False
        elif quoted and value == 92:
            escaped = True
        elif value == 39:
            quoted = not quoted
    return not quoted and not escaped and statement.rstrip().endswith(b";")


def split_insert_rows(statement, expected_columns):
    """Parse the known mysqldump VALUES dialect, retaining every tuple byte."""
    match = INSERT.match(statement)
    if not match or not _statement_complete(statement):
        raise RestoreProofError("Unsupported or truncated INSERT statement")
    values = statement[match.end():].rstrip()
    if not values.endswith(b";"):
        raise RestoreProofError("INSERT terminator is missing")
    values = values[:-1]
    rows = []
    position = 0
    while position < len(values):
        if values[position] != 40:
            raise RestoreProofError("Invalid INSERT tuple separator")
        start = position
        field_start = position + 1
        fields = 1
        quoted = escaped = False
        position += 1
        while position < len(values):
            value = values[position]
            if escaped:
                escaped = False
            elif quoted:
                if value == 92:
                    escaped = True
                elif value == 39:
                    quoted = False
            elif value == 39:
                quoted = True
            elif value == 40:
                raise RestoreProofError("Unexpected nested expression in INSERT tuple")
            elif value in (44, 41):
                if not values[field_start:position].strip():
                    raise RestoreProofError("An INSERT field is empty")
                if value == 44:
                    fields += 1
                    field_start = position + 1
                else:
                    if fields != expected_columns:
                        raise RestoreProofError("INSERT column count differs from saved metadata")
                    rows.append(values[start:position + 1])
                    position += 1
                    break
            elif value == 59:
                raise RestoreProofError("Unexpected statement delimiter in INSERT tuple")
            position += 1
        else:
            raise RestoreProofError("Truncated or unbalanced INSERT tuple")
        if position == len(values):
            return rows
        if values[position:position + 2] != b",(":
            raise RestoreProofError("Invalid INSERT tuple separator")
        position += 1
    raise RestoreProofError("INSERT contains no complete tuples")


def read_dump_rows(stream, column_counts, default_schema=None):
    """Read complete dumps; reject truncation, unsupported INSERTs and absent tables."""
    result = {name: Counter() for name in column_counts}
    schema = default_schema
    seen = set()
    completed = header = False
    pending = None
    pending_name = None
    for line in stream:
        if completed:
            if line.strip():
                raise RestoreProofError("Unexpected content after dump completion footer")
            continue
        if pending is not None:
            pending += line
            if _statement_complete(pending):
                result[pending_name].update(split_insert_rows(pending, column_counts[pending_name]))
                pending = pending_name = None
            continue
        if line.startswith(b"-- MySQL dump "):
            header = True
        if line.startswith(b"-- Dump completed on "):
            completed = True
            continue
        match = USE.fullmatch(line)
        if match:
            schema = match[1].decode("ascii")
            continue
        match = DATA_HEADER.fullmatch(line)
        if match:
            name = f"{schema}.{match[1].decode('ascii')}"
            if name in result:
                seen.add(name)
            continue
        if not line.startswith(b"INSERT"):
            continue
        match = INSERT.match(line)
        if not match:
            raise RestoreProofError("Unsupported INSERT dump format")
        name = f"{schema}.{match[1].decode('ascii')}"
        if name not in result:
            continue
        seen.add(name)
        if _statement_complete(line):
            result[name].update(split_insert_rows(line, column_counts[name]))
        else:
            pending, pending_name = line, name
    if pending is not None or not completed or not header:
        raise RestoreProofError("Dump is truncated or lacks its standard header/footer")
    if seen != set(result):
        raise RestoreProofError("Dump is missing a required table")
    return result


def row_digest(rows):
    """An order-independent, duplicate-sensitive, unambiguously framed digest."""
    digest = hashlib.sha256()
    for row, occurrences in sorted(rows.items()):
        for _ in range(occurrences):
            digest.update(len(row).to_bytes(8, "big"))
            digest.update(row)
    return digest.hexdigest()


def prove_rows(tables, counts, differences, original_stream, restored_reader):
    columns = {name: len(tables[name]) for name in differences}
    saved = read_dump_rows(original_stream, columns)
    proofs = {}
    for name in sorted(differences):
        original_rows = saved[name]
        restored_rows = restored_reader(name, columns[name])
        original_count = sum(original_rows.values())
        restored_count = sum(restored_rows.values())
        if original_count != counts[name] or restored_count != counts[name]:
            raise RestoreProofError("Canonical INSERT row count differs from checkpoint metadata")
        if original_rows != restored_rows:
            raise RestoreProofError("Canonical INSERT tuple multisets differ")
        proofs[name] = {
            "original_row_count": original_count,
            "restored_row_count": restored_count,
            "original_rows_sha256": row_digest(original_rows),
            "restored_rows_sha256": row_digest(restored_rows),
            "raw_checksums": differences[name],
            "float_columns": [column for column, _, kind in tables[name]
                              if re.match(r"float(?:\(|\Z)", kind, re.IGNORECASE)],
        }
    return proofs


def _staging_module():
    spec = importlib.util.spec_from_file_location("coa_staging_capture", Path(__file__).with_name("create-coa-staging.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guard_staging(container, staging):
    info = staging.inspect(container)
    labels = info.get("Config", {}).get("Labels", {})
    project = labels.get("com.docker.compose.project", "")
    if not re.fullmatch(r"coa-staging-[a-z0-9][a-z0-9-]*", project) or labels.get("com.docker.compose.service") != "database":
        raise RestoreProofError("Canonical proof requires an isolated staging database")
    if not info.get("State", {}).get("Running"):
        raise RestoreProofError("The staging database is not running")
    services = staging.output(["docker", "ps", "--filter", f"label=com.docker.compose.project={project}",
                               "--format", '{{.Label "com.docker.compose.service"}}']).splitlines()
    if any(service != "database" for service in services) or services.count("database") != 1:
        raise RestoreProofError("Staging gameplay services must remain stopped during the proof")


def _redump_rows(container, checkpoint, table, columns):
    schema, name = table.split(".")
    errors_path = checkpoint / f"restore-proof-{schema}-{name}.stderr"
    command = ["docker", "exec", container, "sh", "-c",
               'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump --no-defaults --user=root '
               '--skip-lock-tables --quick --hex-blob --set-gtid-purged=OFF --no-tablespaces '
               '--column-statistics=0 --comments --dump-date --extended-insert --skip-complete-insert '
               '--skip-compact "$1" "$2"', "restore-proof-read", schema, name]
    with tempfile.TemporaryFile(mode="w+b") as dump, _private_file(errors_path) as errors:
        result = subprocess.run(command, stdout=dump, stderr=errors, check=False)
        if result.returncode:
            raise RestoreProofError("Read-only staging redump failed; private stderr retained")
        if errors_path.stat().st_size:
            raise RestoreProofError("Read-only staging redump emitted diagnostics; private stderr retained")
        dump.seek(0)
        return read_dump_rows(dump, {table: columns}, default_schema=schema)[table]


def verify_restore(container, checkpoint, expected, restored):
    """Verify and persist private proof; never alter live or staging database rows."""
    checkpoint = Path(checkpoint)
    evidence_path = checkpoint / "restore-canonical-proof.json"
    evidence = {"status": "failed", "proof_kind": "exact-canonical-insert-row-multiset",
                "bit_identical_float_storage": False, "tables": {}}
    try:
        tables, counts, differences = validate_signatures(expected, restored)
        evidence["raw_checksum_deltas"] = differences
        metadata = json.loads((checkpoint / "checkpoint.json").read_text(encoding="utf-8"))
        if metadata.get("database_signature") != expected:
            raise RestoreProofError("Expected signature differs from the saved checkpoint")
        expected_digest = metadata.get("database_dump_sha256", "")
        if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise RestoreProofError("Checkpoint dump SHA-256 is missing or invalid")
        dump_path = checkpoint / "databases.sql"
        with dump_path.open("rb") as stream:
            actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_digest != expected_digest:
            raise RestoreProofError("Checkpoint SQL dump SHA-256 changed")
        evidence["database_dump_sha256"] = actual_digest
        staging = _staging_module()
        _guard_staging(container, staging)
        if differences:
            with dump_path.open("rb") as stream:
                evidence["tables"] = prove_rows(
                    tables, counts, differences, stream,
                    lambda table, columns: _redump_rows(container, checkpoint, table, columns))
        if staging.database_signature(container) != restored:
            raise RestoreProofError("Staging signature changed during the canonical proof")
        _guard_staging(container, staging)
        evidence["status"] = "verified"
        evidence["metadata_unchanged"] = True
        _write_evidence(evidence_path, evidence)
        return evidence
    except (RestoreProofError, OSError, ValueError, RuntimeError) as error:
        # Parser and validation errors are deliberately data-free. External errors
        # must not expose subprocess output, SQL row values, or configuration.
        reason = str(error) if isinstance(error, RestoreProofError) else "Canonical restore proof could not complete"
        evidence["failure_reason"] = reason
        _write_evidence(evidence_path, evidence)
        raise RestoreProofError(reason) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--container", required=True)
    arguments = parser.parse_args()
    checkpoint_metadata = json.loads((arguments.checkpoint / "checkpoint.json").read_text(encoding="utf-8"))
    staging_module = _staging_module()
    try:
        proof = verify_restore(arguments.container, arguments.checkpoint, checkpoint_metadata["database_signature"],
                               staging_module.database_signature(arguments.container))
    except RestoreProofError as error:
        parser.exit(1, f"ERROR: {error}\n")
    print(f"Logical restore verified for {len(proof['tables'])} FLOAT checksum exceptions; private proof saved.")
