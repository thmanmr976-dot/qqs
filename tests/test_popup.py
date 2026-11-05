import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QPlainTextEdit
from PySide6.QtCore import Qt
import app,appearance
from library import source_metadata,infer_legacy_source
QAPP=QApplication.instance() or QApplication([])

class PopupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patches=[patch.object(app,'DATA',self.root/'data'),patch.object(appearance,'CONFIG',self.root/'config'),patch.object(app,'CONFIG',self.root/'config')]
        for p in self.patches:p.start()
    def tearDown(self):
        for widget in QAPP.topLevelWidgets():widget.hide()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_rasi_and_json_migration(self):
        appearance.CONFIG.mkdir()
        old={'background':'#112233','width':940,'height':660,'font_size':17,'footer_text':'Hello Rasi'}
        (appearance.CONFIG/'menu.json').write_text(json.dumps(old))
        theme=appearance.load_theme('menu')
        self.assertEqual(theme['background'],'#112233');self.assertEqual(theme['width'],560)
        self.assertEqual(theme['footer_text'],'Hello Rasi')
        self.assertTrue((appearance.CONFIG/'menu.lua').exists());self.assertTrue((appearance.CONFIG/'menu.json.bak').exists())
        (appearance.CONFIG/'menu.rasi').write_text('window { width: 500px; } footer { text: "Rasi <3"; }')
        self.assertEqual(appearance.load_theme('menu')['width'],500)
    def test_invalid_rasi_is_rejected(self):
        appearance.load_theme('menu')
        (appearance.CONFIG/'menu.rasi').write_text('window { width: nonsense; }')
        with self.assertRaises(ValueError):appearance.load_theme('menu')
    def test_source_provenance_and_legacy_recovery(self):
        meta=source_metadata('https://github.com/owner/repo/tree/main')
        self.assertEqual(meta['source'],'https://github.com/owner/repo/tree/main')
        folder=self.root/'owner-repo-abcdef1';folder.mkdir();entry=folder/'shell.qml';entry.write_text('')
        (folder/'README.md').write_text('https://github.com/other/wrong\nhttps://github.com/owner/repo/stargazers')
        rice=infer_legacy_source({'entry':str(entry),'root':str(self.root)})
        self.assertEqual(rice['source'],'https://github.com/owner/repo')
    def test_import_source_is_persisted(self):
        folder=self.root/'imported';folder.mkdir();(folder/'shell.qml').write_text('import Quickshell\nShellRoot {}')
        w=app.Window();w.monitor.stop()
        try:
            with patch.object(app.QMessageBox,'information'):
                w.imported(str(folder),'From GitHub',{'source_kind':'github','source':'https://github.com/owner/repo'})
            values=json.loads((app.DATA/'preferences.json').read_text())
            self.assertEqual(values['rices'][0]['source'],'https://github.com/owner/repo')
        finally:w.hide();w.deleteLater();QAPP.processEvents()
    def test_preview_actions_compact_and_above(self):
        folder=self.root/'rice';folder.mkdir();entry=folder/'shell.qml';entry.write_text('import Quickshell\nShellRoot {}')
        w=app.Window();w.monitor.stop()
        try:
            rice={'name':'Test','entry':str(entry),'root':str(folder),'source_kind':'github','source':'https://github.com/owner/repo'}
            actions=w.rice_actions(rice);names=[action.text() for action in actions.actions()]
            for name in ('View configuration files…','Open configuration folder','Open shell entry file','Open import page on GitHub','Remove from saved rices','Rename saved rice…'):self.assertIn(name,names)
            self.assertTrue(w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
            self.assertLessEqual(w.width(),560);self.assertLessEqual(w.height(),400)
            dialog=w.preview_files(rice)
            self.assertIn('ShellRoot',dialog.findChild(QPlainTextEdit).toPlainText())
            with patch.object(app.QDesktopServices,'openUrl') as open_url:
                w.open_source(rice);self.assertEqual(open_url.call_args.args[0].toString(),rice['source'])
            self.assertFalse(w.can_trash(rice))
            w.rices=[rice];w.save_list();w.remove_rice(rice)
            self.assertTrue(entry.exists());self.assertEqual(w.rices,[])
        finally:w.hide();w.deleteLater();QAPP.processEvents()
