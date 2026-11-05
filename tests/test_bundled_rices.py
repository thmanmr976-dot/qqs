import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bundled_rices import install_bundled


class BundledRiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bundle = self.root / 'package'
        (self.bundle / 'demo').mkdir(parents=True)
        (self.bundle / 'demo/shell.qml').write_text('import Quickshell\nShellRoot {}')
        self.index = {'rices': [{'id': 'demo', 'name': 'Demo', 'directory': 'demo', 'entry': 'shell.qml', 'source': 'https://github.com/example/demo', 'source_kind': 'github'}]}
        self.write_index()
        self.data = self.root / 'new-machine/data'

    def tearDown(self):
        self.temporary.cleanup()

    def write_index(self):
        (self.bundle / 'index.json').write_text(json.dumps(self.index))

    def test_relocates_paths_and_preserves_user_edits_on_reinstall(self):
        self.assertEqual(install_bundled(self.data, self.bundle), 1)
        prefs = self.data / 'preferences.json'
        value = json.loads(prefs.read_text())
        entry = Path(value['rices'][0]['entry'])
        self.assertTrue(entry.is_relative_to(self.data))
        entry.write_text('user modifications')
        value['rices'][0]['name'] = 'My name'
        value['restore_login'] = True
        prefs.write_text(json.dumps(value))
        self.assertEqual(install_bundled(self.data, self.bundle), 0)
        self.assertEqual(entry.read_text(), 'user modifications')
        self.assertEqual(json.loads(prefs.read_text()), value)

    def test_existing_folders_and_rices_are_kept(self):
        folder = self.data / 'interfaces/bundled-demo'
        folder.mkdir(parents=True)
        (folder / 'mine').write_text('keep')
        (self.data / 'preferences.json').write_text(json.dumps({'rices': [{'name': 'Existing', 'entry': '/existing.qml'}]}))
        self.assertEqual(install_bundled(self.data, self.bundle), 1)
        rices = json.loads((self.data / 'preferences.json').read_text())['rices']
        self.assertEqual(rices[0]['name'], 'Existing')
        self.assertIn('bundled-demo-2', rices[1]['entry'])
        self.assertEqual((folder / 'mine').read_text(), 'keep')

    def test_rejects_escaping_manifest_paths(self):
        self.index['rices'][0]['entry'] = '../../outside.qml'
        self.write_index()
        with self.assertRaises(ValueError):
            install_bundled(self.data, self.bundle)


if __name__ == '__main__':
    unittest.main()
