#!/usr/bin/env python3
"""Check candidate verification guards with fake Git/Docker and temporary files only."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'verify-coa-candidate.sh'
PIN = 'd48a1123153a3c39e1eaafb7714b375ee67e7689'


@unittest.skipUnless(shutil.which('bash'), 'bash is required')
class CandidateVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {name: self.root / name for name in ('source', 'build', 'data', 'cache')}
        for path in self.paths.values():
            path.mkdir()
        (self.paths['source'] / 'conf').mkdir()
        (self.paths['data'] / 'dbc').mkdir()
        (self.paths['data'] / 'dbc' / 'Spell.dbc').touch()
        self.settings = self.paths['source'] / 'conf' / 'verify-all.json'
        self.write_settings()
        fake_bin = self.root / 'bin'
        fake_bin.mkdir()
        self.fake_git = fake_bin / 'git'
        for command, body in (
            ('git', f'printf "%s\\n" "{PIN}"\n'),
            ('docker', 'printf "%s\\n" "$@" > "$COA_G1_TEST_CAPTURE"\n'),
        ):
            executable = fake_bin / command
            executable.write_text('#!/usr/bin/env bash\nset -eu\n' + body)
            executable.chmod(0o700)
        self.capture = self.root / 'docker-arguments'
        self.env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ['PATH'],
                        COA_G1_SOURCE_DIR=str(self.paths['source']),
                        COA_G1_BUILD_DIR=str(self.paths['build']),
                        COA_G1_DATA_DIR=str(self.paths['data']),
                        COA_G1_CCACHE_DIR=str(self.paths['cache']),
                        COA_G1_TEST_CAPTURE=str(self.capture))

    def write_settings(self, **overrides):
        values = {'build_directory': str(self.paths['build']),
                  'dbc_directory': str(self.paths['data'] / 'dbc')}
        values.update(overrides)
        self.settings.write_text(json.dumps(values))

    def run_helper(self, *arguments):
        return subprocess.run(['bash', str(SCRIPT), *arguments], env=self.env,
                              capture_output=True, text=True)

    def assert_refused(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertFalse(self.capture.exists())

    def test_invalid_mode(self):
        result = self.run_helper('deploy')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.capture.exists())

    def test_missing_directory(self):
        self.env['COA_G1_BUILD_DIR'] = str(self.root / 'missing')
        self.assert_refused(self.run_helper(), 'prerequisite directory is missing')

    def test_live_named_directory(self):
        live = self.root / 'wow-server-coa-dev'
        live.mkdir()
        self.env['COA_G1_BUILD_DIR'] = str(live)
        self.assert_refused(self.run_helper(), 'Refusing a live or accepted-baseline directory')

    def test_same_source_and_build(self):
        self.env['COA_G1_BUILD_DIR'] = str(self.paths['source'])
        self.assert_refused(self.run_helper(), 'must be distinct')

    def test_build_override_must_match_settings(self):
        self.write_settings(build_directory=str(self.root / 'other-build'))
        self.assert_refused(self.run_helper(), 'build_directory does not match')

    def test_data_override_must_match_settings(self):
        self.write_settings(dbc_directory=str(self.root / 'other-data'))
        self.assert_refused(self.run_helper(), 'dbc_directory does not match')

    def test_relative_configured_directory_is_rejected(self):
        self.write_settings(build_directory='relative-build')
        self.assert_refused(self.run_helper(), 'must be an absolute configured path')

    def test_non_object_settings_are_rejected(self):
        self.settings.write_text('[]')
        self.assert_refused(self.run_helper(), 'must be a JSON object')

    def test_unreviewed_head_is_rejected(self):
        self.fake_git.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "other-head"\n')
        self.assert_refused(self.run_helper(), 'HEAD does not match')

    def test_plan_uses_bounded_build_and_no_database_access(self):
        result = self.run_helper('plan')
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.capture.read_text().splitlines()
        self.assertIn('--cpus=4', arguments)
        self.assertIn('--memory=10g', arguments)
        self.assertIn('--plan', arguments)
        self.assertIn('source,build,unit,harness', arguments)
        self.assertNotIn('--network', arguments)
        self.assertNotIn('--publish', arguments)
        self.assertFalse(any('docker.sock' in value or 'candidate-runtime' in value for value in arguments))


if __name__ == '__main__':
    unittest.main()
