import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import Runtime, launch_environment

class RuntimeTests(unittest.TestCase):
    def test_recover_and_stop_owned_process(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); binary=root/'fake-qs'
            binary.write_text('#!/usr/bin/env python3\nimport time\nprint("started", flush=True)\ntime.sleep(30)\n'); binary.chmod(0o755)
            entry=root/'shell.qml'; entry.write_text('')
            original=Runtime(root/'data'); original.start(str(binary), str(entry))
            recovered=Runtime(root/'data')
            try:
                self.assertTrue(recovered.alive())
                with self.assertRaises(RuntimeError): recovered.start(str(binary), str(entry))
                recovered.stop()
                for _ in range(100):
                    original.poll(); recovered.poll()
                    if not recovered.alive(): break
                    time.sleep(.03)
                self.assertFalse(recovered.alive())
            finally:
                if original.child.poll() is None: original.child.kill()
                original.child.wait()
    def test_user_qml_path_without_shell_environment(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d); modules = home / '.local/lib/qt6/qml'; modules.mkdir(parents=True)
            env = launch_environment({'PATH': '/usr/bin'}, home)
            self.assertIn(str(modules), env['QML_IMPORT_PATH'].split(os.pathsep))
            self.assertEqual(env['PATH'], '/usr/bin')
    def test_explicit_import_paths_keep_priority(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); modules=home / '.local/lib/qt6/qml'; modules.mkdir(parents=True)
            env=launch_environment({'QML_IMPORT_PATH':'/custom/qml:'+str(modules), 'QML2_IMPORT_PATH':'/legacy/qml'},home)
            self.assertEqual(env['QML_IMPORT_PATH'].split(os.pathsep)[:2], ['/custom/qml',str(modules)])
            self.assertEqual(env['QML_IMPORT_PATH'].split(os.pathsep).count(str(modules)), 1)
            self.assertEqual(env['QML2_IMPORT_PATH'], '/legacy/qml')
    def test_stale_identity_does_not_target_process(self):
        with tempfile.TemporaryDirectory() as d:
            r=Runtime(d); r.state={'pid':os.getpid(), 'start':'invalid'}
            self.assertFalse(r.alive()); r.stop()

if __name__=='__main__': unittest.main()
