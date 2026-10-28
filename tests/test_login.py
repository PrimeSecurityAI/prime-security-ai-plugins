import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-operator/skills/prime/scripts/prime_login.py'


class LoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('prime_login', SCRIPT)
        cls.login = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.login)

    def test_save_token_replaces_loose_file_or_symlink_privately(self):
        for existing in ('loose', 'symlink'):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                token = Path(directory) / 'prime-security/token'; token.parent.mkdir(mode=0o755)
                target = Path(directory) / 'other'; target.write_text('other-dummy-token\n')
                if existing == 'symlink':
                    token.symlink_to(target)
                else:
                    token.write_text('old-dummy-token\n'); token.chmod(0o644)
                with patch.object(self.login, 'TOKEN_FILE', token):
                    self.login.save_token('new-dummy-token')
                self.assertEqual(token.read_text(), 'new-dummy-token\n')
                self.assertFalse(token.is_symlink())
                self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(token.parent.stat().st_mode), 0o700)
                self.assertEqual(list(token.parent.iterdir()), [token])
                self.assertEqual(target.read_text(), 'other-dummy-token\n')
