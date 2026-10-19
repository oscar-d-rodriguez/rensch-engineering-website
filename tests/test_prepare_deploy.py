import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('prepare_deploy', Path(__file__).resolve().parents[1] / 'scripts/prepare_deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeployPayloadTests(unittest.TestCase):
    def test_excludes_account_data_development_logs_and_document_sources(self):
        unsafe = ['.git/config', '.github/workflows/deploy.yml', 'docs/deployment.md',
                  'tests/test.py', 'scripts/tool.py', 'php/error_log', 'php/php.ini',
                  'renschengineering.com/janet/.ftpquota',
                  'new.renschengineering.com/janet/.ftpquota',
                  'images/about/Thumbs.db', 'careers/designer.pages/Index.zip']
        safe = ['index.html', 'css/navigation.css', 'js/custom.js', 'php/contact-form.php',
                'projects/Medical & Vet Projects.pdf', 'careers/Drafter.pdf']
        self.assertEqual(set(deploy.select_site_files(unsafe + safe)), set(safe))

    def test_rejects_path_traversal(self):
        for path in ['/tmp/private', '../private', 'images/../../private']:
            with self.assertRaises(ValueError):
                deploy.select_site_files([path])

    def test_rebuild_removes_only_local_stale_payload_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in deploy.ROOT_FILES:
                (root / name).write_text(name)
            (root / '.deploy').mkdir()
            (root / '.deploy/stale.txt').write_text('local stale payload')
            tracked = '\0'.join(deploy.ROOT_FILES).encode() + b'\0'
            with patch.object(deploy.subprocess, 'check_output', return_value=tracked):
                files = deploy.prepare(root)
            self.assertFalse((root / '.deploy/stale.txt').exists())
            self.assertEqual((root / '.deploy/index.html').read_text(), 'index.html')
            self.assertEqual((root / 'index.html').read_text(), 'index.html')
            self.assertEqual(set(files), deploy.ROOT_FILES)

    def test_missing_required_pages_fails_before_changing_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.deploy').mkdir()
            sentinel = root / '.deploy/existing.txt'
            sentinel.write_text('keep')
            with patch.object(deploy.subprocess, 'check_output', return_value=b'index.html\0'):
                with self.assertRaises(ValueError):
                    deploy.prepare(root)
            self.assertTrue(sentinel.exists())


if __name__ == '__main__':
    unittest.main()
