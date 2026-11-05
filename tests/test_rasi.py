import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import appearance,app
from rasi import read_theme
from customization import matches
from theme_defaults import MENU
from PySide6.QtWidgets import QApplication
QAPP=QApplication.instance() or QApplication([])

class RasiTests(unittest.TestCase):
    def test_import_variables_states_and_comments(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'colors.rasi').write_text('* { accent: #12ab34; }')
            (p/'menu.rasi').write_text('@import "colors.rasi"\n/* outer /* inner */ done */ window {width: 50%; border-color: @accent; } element selected.normal { text-color: #abcdef; } entry { placeholder: "https://github.com/owner/repo"; }')
            values=read_theme(p/'menu.rasi',MENU)
            self.assertEqual(values['width'],'50%');self.assertEqual(values['border_color'],'#12ab34');self.assertEqual(values['row_selected_text_color'],'#abcdef')
            self.assertIn('https://',values['placeholder'])
    def test_import_cycle_and_unknown_selector(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'menu.rasi';p.write_text('@import "menu.rasi"')
            with self.assertRaisesRegex(ValueError,'Circular'):read_theme(p,MENU)
            p.write_text('unsupported { color: red; }')
            with self.assertRaisesRegex(ValueError,'Unsupported'):read_theme(p,MENU)
    def test_matching_modes(self):
        self.assertTrue(matches('prsn','Persona','fuzzy'));self.assertFalse(matches('psrn','Persona','fuzzy'))
        self.assertTrue(matches('per','Persona','prefix'));self.assertFalse(matches('son','Persona','prefix'))
        self.assertTrue(matches('sona','Persona'));self.assertFalse(matches('PERSONA','Persona','substring',True))
    def test_rofi_values_and_padding(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'menu.rasi'
            p.write_text('* { tone: #12345680; } window { background-color: @tone; } mainbox { padding: 10px 20px; children: [ inputbar, listview ]; } configuration { kb-row-down: "Down,Control+j"; }')
            values=read_theme(p,MENU)
            self.assertEqual(values['background'],'#80123456');self.assertEqual(values['layout_padding'],'10px 20px')
            self.assertFalse(values['show_footer']);self.assertTrue(values['layout_order'].startswith('input,list'))
            self.assertEqual(values['keys_next'],'Down,Control+j')
    def test_presets(self):
        for p in (appearance.DEFAULTS/'presets').glob('*.rasi'):
            with self.subTest(theme=p.name):
                v=read_theme(p,MENU,(appearance.DEFAULTS/'presets',));self.assertTrue(v)
    def test_grid_filter_keyboard_and_lua_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);config=root/'config';config.mkdir()
            (config/'menu.lua').write_text('return { width = 540, height = 380, background = "#142033" }')
            with patch.object(appearance,'CONFIG',config),patch.object(app,'CONFIG',config),patch.object(app,'DATA',root/'data'):
                v=appearance.load_theme('menu');self.assertTrue((config/'menu.lua').exists());self.assertEqual(v['background'],'#142033');appearance.set_format('rasi')
                (config/'menu.rasi').write_text('@theme "qqs-grid"\nconfiguration { navigation-wrap: true; }')
                w=app.Window();w.monitor.stop()
                try:
                    w.rices=[{'name':'Persona','entry':str(root/'one.qml')},{'name':'Nordic','entry':str(root/'two.qml')}];w.refresh_list();w.show();QAPP.processEvents();QAPP.processEvents()
                    self.assertEqual(w.list.visualItemRect(w.list.item(0)).y(),w.list.visualItemRect(w.list.item(1)).y())
                    w.source.setText('prsn');self.assertTrue(w.list.item(0).isHidden());self.assertFalse(w.list.item(1).isHidden()) # alphabetical grid: Nordic, Persona
                    w.source.clear();w.list.setCurrentRow(0);w.move_selection(-1);self.assertEqual(w.list.currentRow(),1)
                    with patch.object(w,'select_rice') as select:w.handle_enter();select.assert_called_once()
                    self.assertEqual(w.theme['list_columns'],2)
                finally:w.hide();w.theme_reload.stop();w.deleteLater();QAPP.processEvents()
