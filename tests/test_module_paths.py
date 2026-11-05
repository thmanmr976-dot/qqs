import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import Runtime, launch_environment, write_json
from startup import restore

class ModulePathRegressionTests(unittest.TestCase):
    def test_custom_paths_survive_clean_desktop_launch(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); custom=home/'custom modules'; custom.mkdir(); data=home/'qqs-data'
            first=launch_environment({'QML_IMPORT_PATH':str(custom)},home,data)
            clean=launch_environment({'PATH':'/usr/bin'},home,data)
            self.assertEqual(first['QML_IMPORT_PATH'].split(os.pathsep)[0],str(custom))
            self.assertIn(str(custom),clean['QML_IMPORT_PATH'].split(os.pathsep))
    def test_legacy_paths_and_newly_installed_modules(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d); legacy=home/'legacy';legacy.mkdir();data=home/'qqs-data'
            launch_environment({'QML2_IMPORT_PATH':str(legacy)},home,data)
            late=home/'.local/lib64/qt6/qml';late.mkdir(parents=True)
            env=launch_environment({},home,data)
            self.assertIn(str(legacy),env['QML_IMPORT_PATH'].split(os.pathsep))
            self.assertIn(str(late),env['QML_IMPORT_PATH'].split(os.pathsep))
    def test_corrupt_cache_does_not_block_normal_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);standard=home/'.local/lib/qt6/qml';standard.mkdir(parents=True)
            cache=home/'data/module-paths.json';cache.parent.mkdir();cache.write_text('invalid json')
            env=launch_environment({},home,cache.parent)
            self.assertIn(str(standard),env['QML_IMPORT_PATH'].split(os.pathsep))
            cache.write_text('{"qml_import_paths": "/bad-string"}')
            env=launch_environment({},home,cache.parent)
            self.assertNotIn('/',env['QML_IMPORT_PATH'].split(os.pathsep))
    def test_login_restore_uses_same_environment_with_no_shell_exports(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);home=root/'home';modules=home/'.local/lib/qt6/qml';modules.mkdir(parents=True)
            data=root/'data';write_json(data/'login-restore.json',{'enabled':True})
            entry=root/'shell.qml';entry.write_text('')
            write_json(data/'last-interface.json',{'entry':str(entry)})
            display=root/'wayland-test';display.touch()
            binary=root/'fake-qs';binary.write_text('#!/usr/bin/python3\nimport os,time\nprint(os.environ.get("QML_IMPORT_PATH", "MISSING"),flush=True)\ntime.sleep(30)\n');binary.chmod(0o755)
            runtime=Runtime(data)
            with patch('startup.Runtime',return_value=runtime), patch.dict(os.environ,{'QML_IMPORT_PATH':'','QML2_IMPORT_PATH':'','WAYLAND_DISPLAY':'wayland-test','XDG_RUNTIME_DIR':str(root)}), patch('runtime.Path.home',return_value=home),patch('startup.shutil.which',return_value=str(binary)):
                restore(data)
            try:
                for _ in range(100):
                    if str(modules) in runtime.text():break
                    time.sleep(.01)
                self.assertIn(str(modules),runtime.text())
                self.assertTrue(runtime.alive())
            finally:
                runtime.stop()
                for _ in range(100):
                    runtime.poll()
                    if not runtime.alive():break
                    time.sleep(.03)
                runtime.child.wait(timeout=3)
    def test_atomic_cache_write_preserves_previous_file_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'module-paths.json';write_json(p,{'before':True})
            with self.assertRaises(TypeError):write_json(p,object())
            self.assertEqual(json.loads(p.read_text()),{'before':True})
            self.assertEqual([f.name for f in p.parent.iterdir()],['module-paths.json'])

if __name__=='__main__':unittest.main()
