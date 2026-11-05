import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QMessageBox
import app
import appearance
from library import resolve_source, entry_files
from install import install

QAPP=QApplication.instance() or QApplication([])

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(app,'DATA',self.root/'data'),patch.object(appearance,'CONFIG',self.root/'config'),patch.object(app,'CONFIG',self.root/'config'),patch.object(QMessageBox,'information'),patch.object(QMessageBox,'warning')]
        for p in self.patches:p.start()
        self.window=app.Window(); self.window.monitor.stop()
    def tearDown(self):
        if self.window.loader:self.window.loader.hide()
        self.window.runtime.stop()
        for _ in range(100):
            self.window.runtime.poll()
            if not self.window.runtime.alive():break
            time.sleep(.03)
        if self.window.runtime.child:self.window.runtime.child.wait(timeout=3)
        for w in QAPP.topLevelWidgets():w.hide()
        self.window.deleteLater(); QAPP.processEvents()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_add_local_persist_duplicate_and_error_log(self):
        folder=self.root/'My Rice';folder.mkdir();(folder/'shell.qml').write_text('import Quickshell\nShellRoot {}')
        self.window.imported(str(folder),'My Rice')
        self.assertEqual(self.window.list.count(),1)
        self.window.imported(str(folder),'My Rice');self.assertEqual(self.window.list.count(),1)
        other=app.Window();other.monitor.stop();self.assertEqual(other.rices[0]['name'],'My Rice');other.hide()
        self.window.failure('A useful import error')
        self.assertIn('A useful import error',(app.DATA/'qqs.log').read_text())
        self.assertTrue(self.window.log_dialog.isVisible())
    def test_source_resolution_and_ambiguity(self):
        self.assertEqual(resolve_source('https://github.com/owner/repo/tree/main')[0],'github')
        with self.assertRaises(ValueError):resolve_source('https://example.com/owner/repo')
        with self.assertRaises(ValueError):resolve_source(str(self.root/'missing'))
        (self.root/'One.qml').write_text('');(self.root/'Two.qml').write_text('')
        with self.assertRaises(ValueError):entry_files(self.root)
    def test_switch_loading_and_survive_close(self):
        binary=self.root/'fake-qs';binary.write_text('#!/usr/bin/env python3\nimport time\nprint("INFO: Configuration Loaded",flush=True)\ntime.sleep(60)');binary.chmod(0o755)
        one=self.root/'one.qml';one.write_text('');two=self.root/'two.qml';two.write_text('')
        self.window.rices=[{'name':'One','entry':str(one)},{'name':'Two','entry':str(two)}];self.window.refresh_list()
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'test'}), patch('app.quickshell_binary',return_value=str(binary)):
            for index in (0,1):
                self.window.select_rice(self.window.list.item(index));self.assertIsNotNone(self.window.loader)
                deadline=time.monotonic()+5
                while self.window.phase and time.monotonic()<deadline:
                    self.window.poll_runtime()
                    if self.window.phase=='starting':self.window.started-=2
                    QAPP.processEvents();time.sleep(.03)
                self.assertIsNone(self.window.phase)
                self.assertTrue(self.window.runtime.alive())
                self.assertEqual(self.window.runtime.state['entry'],str((one,two)[index]))
        self.window.close(); self.assertTrue(self.window.runtime.alive())
    def test_non_quickshell_entry_runs_without_quickshell_readiness(self):
        entry=self.root/'main.py';entry.write_text('import time\nprint("CUSTOM_STARTED",flush=True)\ntime.sleep(60)')
        self.window.imported(str(entry),'Custom shell')
        self.assertEqual(self.window.rices[0]['backend'],'custom')
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'test'}),patch('app.quickshell_binary',side_effect=AssertionError('Quickshell should not be used')):
            self.window.select_rice(self.window.list.item(0))
            deadline=time.monotonic()+5;aged=False
            while self.window.phase and time.monotonic()<deadline:
                self.window.poll_runtime()
                if self.window.phase=='starting' and not aged:self.window.started-=2;aged=True
                QAPP.processEvents();time.sleep(.03)
        self.assertIsNone(self.window.phase);self.assertTrue(self.window.runtime.alive())
        self.assertEqual(self.window.runtime.state['backend'],'custom')
        self.assertNotIn('Configuration Loaded',self.window.runtime.text())
    def test_missing_backend_does_not_stop_current_shell(self):
        entry=self.root/'app.ts';entry.write_text('import app from "ags/gtk4/app"')
        self.window.rices=[{'name':'AGS','entry':str(entry)}];self.window.refresh_list()
        with patch('backends.shutil.which',return_value=None),patch.object(self.window.runtime,'stop') as stop,patch.object(self.window,'failure') as failed:
            self.window.select_rice(self.window.list.item(0));stop.assert_not_called();failed.assert_called_once()
        self.assertIsNone(self.window.loader)
    def test_themes_and_installer(self):
        theme=appearance.load_theme('menu');self.assertIn('corner_radius',theme)
        p=appearance.CONFIG/'menu.rasi';p.write_text('window { broken rasi')
        with self.assertRaises(ValueError):appearance.load_theme('menu')
        config=self.root/'xdg'; lua=config/'hypr/hyprland.lua';lua.parent.mkdir(parents=True);lua.write_text('-- original\n')
        with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(config),'XDG_DATA_HOME':str(self.root/'xdg-data')}):install();install()
        self.assertEqual(lua.read_text().count('hl.bind("CTRL + SHIFT + Q"'),1)
        self.assertTrue((self.root/'xdg-data/applications/qqs.desktop').exists())

if __name__=='__main__':unittest.main()
