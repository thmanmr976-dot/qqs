import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QPushButton
import app,appearance
from theme_defaults import MENU,LOADING
from ui_text import source_action,shortcut_hint,startup_failure
QAPP=QApplication.instance() or QApplication([])

class InterfaceWordingTests(unittest.TestCase):
    def test_source_labels_describe_destination(self):
        self.assertEqual(source_action({'source_kind':'github','source':'https://github.com/a/b'}),'Open import page on GitHub')
        self.assertEqual(source_action({'source_kind':'zip','source':'/tmp/rice.zip'}),'Open original ZIP archive')
        self.assertEqual(source_action({'source_kind':'local','source':'/tmp/rice'}),'Open original folder')
        self.assertEqual(source_action({'source_kind':'local','source':'/tmp/shell.qml'}),'Open original entry file')
        self.assertEqual(source_action({}),'Import source unavailable')
    def test_footer_matches_keys_and_action(self):
        theme={**MENU,'keys_accept':'F2','keys_add':'Ctrl+i','keys_close':'F8'}
        self.assertIn('F2: start selected rice',shortcut_hint(theme,'Persona'))
        self.assertIn('F2: import source',shortcut_hint(theme,'https://github.com/a/b'))
        self.assertIn('Ctrl+I: import',shortcut_hint(theme))
        self.assertIn('F8: hide',shortcut_hint(theme))
    def test_startup_error_does_not_invent_exit_code(self):
        self.assertNotIn('None',startup_failure(None));self.assertNotIn('code',startup_failure(None))
        self.assertIn('255',startup_failure(255))
    def test_log_buttons_open_the_named_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'data';data.mkdir()
            (data/'qqs.log').write_text('launcher error');(data/'session.log').write_text('quickshell output')
            with patch.object(app,'DATA',data),patch.object(appearance,'CONFIG',root/'config'),patch.object(app,'CONFIG',root/'config'):
                w=app.Window();w.monitor.stop()
                try:
                    w.show_logs();buttons={b.text():b for b in w.log_dialog.findChildren(QPushButton)}
                    with patch.object(app.QDesktopServices,'openUrl') as opened:
                        buttons['Open launcher log'].click();self.assertEqual(opened.call_args.args[0].toLocalFile(),str(data/'qqs.log'))
                        buttons['Open shell log'].click();self.assertEqual(opened.call_args.args[0].toLocalFile(),str(data/'session.log'))
                    w.stop_rice();self.assertEqual(w.status.text(),'No rice started by qqs is running.')
                finally:
                    w.log_dialog.hide();w.theme_reload.stop();w.hide();w.deleteLater();QAPP.processEvents()
    def test_loading_caption_contains_the_selected_rice_name(self):
        screen=app.Loading({**LOADING,'message':LOADING['message'].replace('{rice}','Persona')})
        self.assertEqual(screen.theme['message'],'Switching to Persona…');screen.hide();screen.deleteLater()
