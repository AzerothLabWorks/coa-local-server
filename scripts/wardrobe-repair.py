#!/usr/bin/env python3
"""Audit or recover the qualified Blood Elf female Scribe models, using local assets only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from wardrobe_mpq import member_rows, name_hash, numeric_inventory, verify_identity

SPEC = importlib.util.spec_from_file_location('client_patch_common', ROOT / 'scripts/client-patches.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
MANIFEST = ROOT / 'client-patches/coa-wardrobe/manifest.json'
require, sha, plain, beneath = C.require, C.sha, C.plain, C.beneath


def windows_path(path):
    path = plain(path)
    if os.name == 'nt':
        return str(path)
    parts = path.parts
    require(len(parts) > 3 and parts[1] == 'mnt' and len(parts[2]) == 1,
            'WSL MPQ operations require paths under /mnt/<drive>; install/rollback use Windows Python')
    return parts[2].upper() + ':\\' + '\\'.join(parts[3:])


class Mpq:
    def __init__(self, tool, expected):
        self.tool, self.expected = plain(tool), expected
        require(sha(self.tool) == expected, 'MPQ tool differs from the reviewed build')

    def call(self, *args):
        require(sha(self.tool) == self.expected, 'MPQ tool changed')
        result = subprocess.run([str(self.tool), *[windows_path(x) if isinstance(x, Path) else x for x in args]],
                                check=True, capture_output=True)
        return result.stdout

    def read(self, archive, member):
        return self.call('read', member.replace('/', '\\'), archive)

    def replace(self, archive, member, source):
        # Both LCID 0 and 0x409 display as enUS in this tool. Omit --locale for
        # neutral 0; numeric MPQ identities are independently verified afterward.
        return self.call('add', '--overwrite', '--path', member.replace('/', '\\'), archive, source)


def recipe():
    data = C.read_json(MANIFEST)
    require(data['schema'] == 1 and len(data['members']) == 2, 'Unsupported repair manifest')
    for key in ('archive', 'donor_archive'):
        C.relative(data[key])
    for item in data['members']:
        C.relative(item['path'])
        C.relative(item['skin'])
        require(item['locale'] == 0, 'Only the qualified neutral-locale repair is supported')
        require(all(re.fullmatch(r'[0-9a-f]{64}', item[key]) for key in
                    ('broken_sha256', 'repaired_sha256', 'skin_sha256')), 'Invalid asset fingerprint')
    return data


def pair(name):
    return (name_hash(name.replace('/', '\\'), 1), name_hash(name.replace('/', '\\'), 2))


def identity(row):
    return tuple(row[k] for k in ('hash1', 'hash2', 'locale', 'platform', 'reserved'))


def neutral_unique(rows, member):
    found = member_rows(rows, member.replace('/', '\\'))
    require(len(found) == 1 and all(found[0][key] == 0 for key in ('locale', 'platform', 'reserved')),
            'Missing, duplicate or non-neutral member requires review: ' + member)
    return found[0]


def archive_paths(client):
    # Inspect locale subdirectories too. No assumed alphabetical load order:
    # an additional provider of either model/skin requires review.
    data = beneath(client, 'Data')
    require(data.is_dir(), 'Client Data directory is missing')
    result = []
    for base, directories, files in os.walk(data, followlinks=False):
        for name in directories:
            plain(Path(base) / name)
        for name in files:
            if Path(name).suffix.lower() == '.mpq':
                result.append(plain(Path(base) / name))
    return sorted(result)


def inspect_client(client, manifest, mpq):
    client = plain(client)
    require(client.is_dir(), 'Client directory is missing')
    C.protected_identity(client, manifest)
    target, donor = [beneath(client, manifest[k]) for k in ('archive', 'donor_archive')]
    target_hash = sha(target)
    wanted = {x[k]: pair(x[k]) for x in manifest['members'] for k in ('path', 'skin')}
    providers = {name: [] for name in wanted}
    target_rows = None
    archives = archive_paths(client)
    states = {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in archives}
    for archive in archives:
        rows = numeric_inventory(archive)
        keys = {(r['hash1'], r['hash2']) for r in rows}
        for name, hashes in wanted.items():
            if hashes in keys:
                neutral_unique(rows, name)
                providers[name].append(archive)
        if archive == target:
            target_rows = rows
    require(target_rows is not None, 'Target archive missing')
    member_states = []
    for item in manifest['members']:
        require(set(providers[item['path']]) == {target, donor},
                'Changed model providers require review: ' + item['path'])
        require(providers[item['skin']] == [donor], 'Changed skin providers require review: ' + item['skin'])
        donor_bytes, skin_bytes = mpq.read(donor, item['path']), mpq.read(donor, item['skin'])
        require(C.digest(donor_bytes) == item['repaired_sha256'], 'Unknown donor model: ' + item['path'])
        require(C.digest(skin_bytes) == item['skin_sha256'], 'Unknown paired skin: ' + item['skin'])
        value = C.digest(mpq.read(target, item['path']))
        if value == item['repaired_sha256']:
            state = 'fixed'
        elif value == item['broken_sha256']:
            state = 'broken'
        else:
            raise ValueError('Unknown model may be newer; review instead of overwriting: ' + item['path'])
        member_states.append({'path': item['path'], 'sha256': value, 'state': state})
    require(archive_paths(client) == archives, 'Archive set changed during audit')
    require(all((p.stat().st_size, p.stat().st_mtime_ns) == states[str(p)] for p in archives),
            'Client archive changed during audit')
    require(sha(target) == target_hash, 'Target archive changed during audit')
    C.protected_identity(client, manifest)
    fixed = all(x['state'] == 'fixed' for x in member_states)
    if not fixed:
        require(all(x['state'] == 'broken' for x in member_states)
                and target_hash in manifest['repairable_archive_sha256']
                and len(target_rows) == manifest['archive_members'],
                'Changed or partially repaired archive requires review')
    return {'status': 'fixed' if fixed else 'repair-needed', 'manifest_id': manifest['id'],
            'archive_sha256': target_hash, 'members': member_states, 'archives_checked': len(archives),
            'numeric_members': len(target_rows), 'client_modified': False}


def audit(args):
    try:
        manifest = recipe()
        report = inspect_client(args.client, manifest, Mpq(args.mpq_tool, manifest['mpqcli_sha256']))
        print(json.dumps(report, indent=2))
        return 0 if report['status'] == 'fixed' else 2
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'review-required', 'reason': str(error), 'client_modified': False}, indent=2))
        return 3


def block_hash(stream, row):
    stream.seek(row['offset'])
    remaining, result = row['compressed_size'], hashlib.sha256()
    while remaining:
        chunk = stream.read(min(remaining, 1024 * 1024))
        require(bool(chunk), 'Truncated archive block')
        result.update(chunk)
        remaining -= len(chunk)
    return result.hexdigest()


def verify_candidate(backup, candidate, manifest, mpq):
    verify_identity(backup, candidate)
    before, after = numeric_inventory(backup), numeric_inventory(candidate)
    require(len(before) == manifest['archive_members'], 'Unexpected member count')
    indexed = {identity(row): row for row in after}
    require(len(indexed) == len(after), 'Duplicate numeric identities')
    excluded = {pair(x['path']) for x in manifest['members']} | {pair('(listfile)'), pair('(attributes)')}
    preserved = 0
    with plain(backup).open('rb') as old, plain(candidate).open('rb') as new:
        for row in before:
            replacement = indexed[identity(row)]
            if (row['hash1'], row['hash2']) in excluded:
                continue
            require(all(row[k] == replacement[k] for k in ('offset', 'compressed_size', 'size', 'flags')),
                    'Unrelated archive metadata changed')
            require(block_hash(old, row) == block_hash(new, replacement), 'Unrelated archive contents changed')
            preserved += 1
    for item in manifest['members']:
        neutral_unique(before, item['path'])
        neutral_unique(after, item['path'])
        require(C.digest(mpq.read(backup, item['path'])) == item['broken_sha256'], 'Unrecognized original model')
        require(C.digest(mpq.read(candidate, item['path'])) == item['repaired_sha256'], 'Prepared model mismatch')
    return {'numeric_members': len(before), 'unrelated_members_preserved': preserved}


def source_identity():
    return {name: sha(ROOT / name) for name in ('scripts/wardrobe-repair.py', 'scripts/wardrobe_mpq.py',
            'scripts/client-patches.py', 'client-patches/coa-wardrobe/manifest.json')}


def snapshot_recipe(artifacts, sources):
    destination = beneath(artifacts, 'recipe')
    require(not destination.exists(), 'Recipe snapshot already exists')
    for name, expected in sources.items():
        target = beneath(destination, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(beneath(ROOT, name), target)
        require(sha(target) == expected, 'Recipe changed while saving recovery tools')


def artifact_paths(client, artifacts):
    client, artifacts = plain(client), plain(artifacts)
    require(client.is_dir() and artifacts.parent.is_dir(), 'Missing client or artifact parent directory')
    require(not artifacts.is_relative_to(client) and not client.is_relative_to(artifacts), 'Overlapping artifact/client paths')
    require(not artifacts.is_relative_to(ROOT), 'Keep private game assets outside the repository')
    require(windows_path(client)[:2].lower() == windows_path(artifacts)[:2].lower(), 'Keep artifacts on the client drive')
    return client, artifacts


def prepare(args):
    client, artifacts = artifact_paths(args.client, args.artifacts)
    require(not artifacts.exists(), 'Choose a new artifact directory')
    manifest = recipe()
    mpq = Mpq(args.mpq_tool, manifest['mpqcli_sha256'])
    report = inspect_client(client, manifest, mpq)
    if report['status'] == 'fixed':
        print('Wardrobe models are already repaired; no files changed.')
        return 0
    sources = source_identity()
    artifacts.mkdir(mode=0o700)
    target = beneath(client, manifest['archive'])
    backup, candidate = artifacts / 'archive.before.mpq', artifacts / 'archive.prepared.mpq'
    shutil.copyfile(target, backup)
    shutil.copyfile(backup, candidate)
    require(sha(backup) == sha(candidate) == report['archive_sha256'], 'Backup copy changed')
    donor = beneath(client, manifest['donor_archive'])
    for index, item in enumerate(manifest['members']):
        value = mpq.read(donor, item['path'])
        require(C.digest(value) == item['repaired_sha256'], 'Donor changed during preparation')
        replacement = artifacts / ('replacement-' + str(index) + '.m2')
        replacement.write_bytes(value)
        mpq.replace(candidate, item['path'], replacement)
    qualification = verify_candidate(backup, candidate, manifest, mpq)
    require(inspect_client(client, manifest, mpq) == report, 'Client changed during preparation')
    require(source_identity() == sources, 'Recipe changed during preparation')
    snapshot_recipe(artifacts, sources)
    proof = {'schema': 1, 'status': 'prepared', 'manifest_id': manifest['id'], 'client': str(client),
             'artifacts': str(artifacts), 'before': report['archive_sha256'], 'after': sha(candidate),
             'source_identity': sources, 'source_snapshot': 'recipe', 'qualification': qualification, 'utc': C.now()}
    C.save(artifacts / 'prepared.json', proof)
    print(json.dumps(proof, indent=2))
    return 0


def load_proof(args):
    C.require_closed()
    client, artifacts = artifact_paths(args.client, args.artifacts)
    manifest = recipe()
    mpq = Mpq(args.mpq_tool, manifest['mpqcli_sha256'])
    proof = C.read_json(artifacts / 'prepared.json')
    # A WSL-prepared receipt uses /mnt/<drive>; compare its Windows equivalent.
    def equivalent(value, expected):
        if value.startswith('/mnt/'):
            parts = Path(value).as_posix().split('/')
            value = parts[2].upper() + ':/' + '/'.join(parts[3:])
        return value.replace('\\', '/').casefold() == windows_path(expected).replace('\\', '/').casefold()
    require(proof['schema'] == 1 and proof['status'] == 'prepared' and proof['manifest_id'] == manifest['id']
            and equivalent(proof['client'], client) and equivalent(proof['artifacts'], artifacts)
            and proof['source_identity'] == source_identity(), 'Prepared receipt does not match this client/recipe')
    require(proof['before'] in manifest['repairable_archive_sha256'], 'Unknown original archive')
    backup, candidate = artifacts / 'archive.before.mpq', artifacts / 'archive.prepared.mpq'
    require(sha(backup) == proof['before'] and sha(candidate) == proof['after'], 'Recovery package changed')
    require(verify_candidate(backup, candidate, manifest, mpq) == proof['qualification'], 'Archive qualification differs')
    return client, artifacts, manifest, mpq, proof


def install(args):
    client, artifacts, manifest, mpq, proof = load_proof(args)
    require(not (artifacts / 'attempt.json').exists(), 'Already attempted; use rollback or new preparation')
    report = inspect_client(client, manifest, mpq)
    require(report['status'] == 'repair-needed' and report['archive_sha256'] == proof['before'],
            'Installed archive changed after preparation')
    C.save(artifacts / 'attempt.json', {'prepared_sha256': sha(artifacts / 'prepared.json'), 'utc': C.now()})
    C.replace_file(beneath(client, manifest['archive']), artifacts / 'archive.prepared.mpq', proof['before'], proof['after'])
    require(inspect_client(client, manifest, mpq)['status'] == 'fixed', 'Installed readback did not pass')
    C.save(artifacts / 'installed.json', {'status': 'installed', 'utc': C.now(), 'archive_sha256': proof['after']})
    print('Wardrobe repair installed; full 3D previews retained. Keep the verified backup and test in game.')
    return 0


def rollback(args):
    client, artifacts, manifest, mpq, proof = load_proof(args)
    require(C.read_json(artifacts / 'attempt.json')['prepared_sha256'] == sha(artifacts / 'prepared.json'),
            'Install attempt does not match this receipt')
    target = beneath(client, manifest['archive'])
    current = sha(target)
    require(current in (proof['before'], proof['after']), 'Archive changed since installation; manual review required')
    if current == proof['after']:
        C.replace_file(target, artifacts / 'archive.before.mpq', proof['after'], proof['before'])
    require(sha(target) == proof['before'], 'Rollback verification failed')
    print('Restored this operation\'s original archive. This reintroduces its known Scribe defect.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'prepare', 'install', 'rollback'))
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--mpq-tool', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path)
    args = parser.parse_args(argv)
    if args.action != 'audit' and args.artifacts is None:
        parser.error('--artifacts is required')
    try:
        return globals()[args.action](args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('Wardrobe repair stopped: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
