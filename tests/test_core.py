import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import extract_archive, github_url, save_text

class Tests(unittest.TestCase):
    def test_github(self):
        self.assertEqual(github_url('https://github.com/a/b.git', 'feature/test'), 'https://api.github.com/repos/a/b/zipball/feature%2Ftest')
        for url in ['http://github.com/a/b', 'https://evil.com/a/b', 'https://github.com/a/b/tree/main']:
            with self.assertRaises(ValueError): github_url(url)
    def test_import_save_collision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); archive = root/'theme.zip'
            with zipfile.ZipFile(archive, 'w') as z: z.writestr('repo/shell.qml', 'import Quickshell\nShellRoot {}')
            one = extract_archive(archive, root/'library'); two = extract_archive(archive, root/'library')
            self.assertNotEqual(one, two)
            f = one/'repo/shell.qml'; previous = f.read_text(); save_text(f, 'changed')
            self.assertEqual(f.read_text(), 'changed'); self.assertEqual(f.with_name('shell.qml.bak').read_text(), previous)
    def test_reject_traversal_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ['../../escape.qml', '/tmp/escape.qml', 'file.txt']:
                archive = root/'bad.zip'
                with zipfile.ZipFile(archive, 'w') as z: z.writestr(name, 'bad')
                with self.assertRaises(ValueError): extract_archive(archive, root/'library')
                self.assertEqual(list((root/'library').iterdir()), [])

if __name__ == '__main__': unittest.main()
