"""The one-shot entry point must not acquire publication or messaging authority."""
from pathlib import Path
import unittest
import yaml


class FixedPreviewWorkflowTests(unittest.TestCase):
    def test_manual_only_preview_with_bounded_inputs_and_artifacts(self):
        path = Path('.github/workflows/publishing-v2-fixed-preview.yml')
        self.assertTrue(path.is_file(), 'manual fixed-preview entry point missing')
        raw = path.read_text()
        workflow = yaml.safe_load(raw)
        triggers = workflow.get('on', workflow.get(True))
        self.assertEqual(set(triggers), {'workflow_dispatch'})
        inputs = triggers['workflow_dispatch']['inputs']
        self.assertEqual(set(inputs), {'lane', 'selection'})
        self.assertEqual(inputs['lane']['options'], ['daily', 'local'])
        self.assertTrue(inputs['selection']['required'])
        job = workflow['jobs']['preview']
        self.assertIn("github.ref == 'refs/heads/main'", job['if'])
        self.assertEqual(workflow['concurrency']['group'], 'executivesaudi-approved-api')
        self.assertFalse(workflow['concurrency']['cancel-in-progress'])
        run = next(s for s in job['steps'] if s.get('name') == 'Prepare one fixed information draft')
        self.assertIn('--mode fixed-preview', run['run'])
        self.assertEqual(run['env']['DRY_RUN'], '1')
        self.assertEqual(run['env']['POST_TO_SNAPCHAT'], '0')
        self.assertEqual(run['env']['AUTOPILOT_MODE'], 'fixed-preview')
        for forbidden in ('BUNDLE_API_KEY', 'BUNDLE_TEAM_ID', 'TELEGRAM_TOKEN',
                          'review_sheet', 'autopilot.report', 'information-publish-request',
                          'prepare-preview', 'git push'):
            self.assertNotIn(forbidden, raw)
        upload = next(s for s in job['steps'] if s.get('uses', '').startswith('actions/upload-artifact@'))
        self.assertEqual(upload['if'], 'always()')
        self.assertIn('autopilot-output/', upload['with']['path'])
        self.assertIn('${{ steps.package.outputs.path }}', upload['with']['path'])
        self.assertNotIn('approved/tawari-*', upload['with']['path'])

    def test_invalid_briefs_stop_before_the_paid_step(self):
        import json
        import os
        import subprocess
        import sys
        import tempfile
        workflow = yaml.safe_load(Path('.github/workflows/publishing-v2-fixed-preview.yml').read_text())
        steps = workflow['jobs']['preview']['steps']
        preflight = next(s for s in steps if s.get('name') == 'Validate explicit evidence brief before paid work')
        paid = next(s for s in steps if s.get('name') == 'Prepare one fixed information draft')
        self.assertLess(steps.index(preflight), steps.index(paid))
        script = preflight['run'].split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            brief = Path(tmp) / 'brief.json'
            brief.write_text(json.dumps({'version': 1, 'lane': 'daily'}))
            def run(path, lane):
                return subprocess.run([sys.executable, '-c', script],
                    env={**os.environ, 'SELECTION': str(path), 'LANE': lane},
                    capture_output=True, text=True)
            self.assertEqual(run(brief, 'daily').returncode, 0)
            self.assertNotEqual(run(brief, 'local').returncode, 0)
            self.assertNotEqual(run(brief, 'both').returncode, 0)
            self.assertNotEqual(run(brief.with_name('missing.json'), 'daily').returncode, 0)
            self.assertNotEqual(run('/etc/passwd', 'daily').returncode, 0)

    def test_artifact_path_is_exact_new_safe_package_only(self):
        import json
        import os
        import subprocess
        import sys
        import tempfile
        workflow = yaml.safe_load(Path('.github/workflows/publishing-v2-fixed-preview.yml').read_text())
        step = next(s for s in workflow['jobs']['preview']['steps'] if s.get('id') == 'package')
        script = step['run'].split("python - <<'PYTHON'\n", 1)[1].rsplit('\nPYTHON', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            output = root / 'output'
            summary = root / 'autopilot-output/summary.json'
            summary.parent.mkdir()
            value = 'approved/tawari-20261104-daily-0123456789ab'
            package = root / value
            package.mkdir(parents=True)
            (package / 'manifest.json').write_text('{}')
            def run(path):
                output.write_text('')
                summary.write_text(json.dumps({'mode': 'fixed-preview', 'results': [
                    {'information_package': {'package': path}}]}))
                result = subprocess.run([sys.executable, '-c', script], cwd=tmp,
                    env={**os.environ, 'GITHUB_OUTPUT': str(output)}, capture_output=True, text=True)
                return result, output.read_text()
            result, emitted = run(value)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(emitted, 'path=' + value + '/\n')
            for invalid in ('../approved/a', '/tmp/approved/a', 'approved/tawari-*', value + '\ninjected=x'):
                result, emitted = run(invalid)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(emitted, '')
            (package / 'link').symlink_to('/etc/passwd')
            self.assertNotEqual(run(value)[0].returncode, 0)
            (package / 'link').unlink()
            subprocess.run(['git', 'add', value], cwd=tmp, check=True)
            self.assertNotEqual(run(value)[0].returncode, 0)
