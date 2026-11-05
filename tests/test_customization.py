import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import appearance,app
from legacy_lua import write_lua
from rasi import read_theme
from theme_defaults import MENU
QAPP=QApplication.instance() or QApplication([])

class CustomizationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=self.root/'config';self.config.mkdir()
        self.patches=[patch.object(appearance,'CONFIG',self.config),patch.object(app,'CONFIG',self.config),patch.object(app,'DATA',self.root/'data')]
        for p in self.patches:p.start()
        self.window=app.Window();self.window.monitor.stop()
    def tearDown(self):
        self.window.theme_reload.stop();self.window.grid_delay.stop();self.window.hide();self.window.deleteLater();QAPP.processEvents()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_lua_grid_layout_and_roundtrip_format(self):
        write_lua(self.config/'menu.lua',{'preset':'qqs-grid','width':640,'input_position':'bottom','row_selected':'#123456','search_mode':'fuzzy'})
        self.window.reload_appearance();self.window.show();QAPP.processEvents()
        self.assertEqual(self.window.theme['list_columns'],2)
        self.assertGreater(self.window.layout().indexOf(self.window.input_widget),self.window.layout().indexOf(self.window.list))
        appearance.set_format('rasi');self.assertEqual(appearance.load_theme('menu')['row_selected'],'#123456')
        appearance.set_format('lua');self.assertEqual(appearance.load_theme('menu')['width'],640)
        self.assertTrue((self.config/'menu.lua.bak').exists())
    def test_failed_live_reload_keeps_style_query_and_selection(self):
        w=self.window;w.rices=[{'name':'Persona','entry':'/test/a.qml'},{'name':'Nordic','entry':'/test/b.qml'}];w.refresh_list();w.source.setText('Persona')
        before=dict(w.theme);style=w.styleSheet()
        (self.config/'menu.lua').write_text('return { background = "not-a-color" }')
        with patch.object(w,'failure') as failure:
            w.reload_appearance(live=True);failure.assert_not_called()
        self.assertEqual(w.theme,before);self.assertEqual(w.styleSheet(),style)
        self.assertEqual(w.source.text(),'Persona');self.assertEqual(w.list.currentItem().data(Qt.ItemDataRole.UserRole)['entry'],'/test/a.qml')
        self.assertIn('Theme reload rejected',(app.DATA/'qqs.log').read_text())
        write_lua(self.config/'menu.lua',{'width':500});w.reload_appearance(live=True);self.assertEqual(w.width(),500)
    def test_failed_background_or_stylesheet_restores_previous_appearance(self):
        w=self.window;before=dict(w.theme);style=w.styleSheet()
        write_lua(self.config/'menu.lua',{'width':700,'background':'#111111','stylesheet_file':'missing.qss'})
        with patch.object(w,'failure'):w.reload_appearance()
        self.assertEqual(w.theme,before);self.assertEqual(w.styleSheet(),style);self.assertEqual(w.width(),before['width'])
    def test_live_watcher_reads_atomic_saves(self):
        w=self.window;w.show();QAPP.processEvents()
        tmp=self.config/'saved.tmp';write_lua(tmp,{'width':510});tmp.replace(self.config/'menu.lua')
        import time
        end=time.monotonic()+2
        while time.monotonic()<end and w.width()!=510:QAPP.processEvents();time.sleep(.02)
        self.assertEqual(w.width(),510)
    def test_bad_loading_timeout_and_search_fields_rejected(self):
        write_lua(self.config/'loading.lua',{'minimum_display_ms':5000,'startup_timeout_ms':1000})
        with self.assertRaisesRegex(ValueError,'startup-timeout'):appearance.load_theme('loading')
        write_lua(self.config/'menu.lua',{'search_fields':'unknown'})
        with self.assertRaisesRegex(ValueError,'search-fields'):appearance.load_theme('menu')
    def test_custom_images_and_loading_screen_style(self):
        from PySide6.QtGui import QPixmap,QColor
        pixmap=QPixmap(80,50);pixmap.fill(QColor('#33aa66'));asset=self.config/'custom.png';pixmap.save(str(asset))
        write_lua(self.config/'menu.lua',{'logo_file':'custom.png','row_icon_file':'custom.png','show_icons':True,'background_image':'custom.png'})
        self.window.reload_appearance();self.assertTrue(self.window.logo.custom_image)
        self.assertEqual(self.window.logo.source_rect.width(),80);self.assertFalse(self.window.row_icon.isNull())
        self.assertFalse(self.window.background_pixmap.isNull())
        write_lua(self.config/'loading.lua',{'background_image':'custom.png','background_image_opacity':70,'bar_style':'line','fullscreen':False})
        loading=app.Loading(appearance.load_theme('loading'));loading.resize(500,300);loading.show();QAPP.processEvents()
        self.assertFalse(loading.image.isNull());self.assertFalse(loading.grab().isNull());loading.hide();loading.deleteLater()
    def test_original_preset_restores_original_appearance(self):
        self.window.apply_preset('qqs-liquid-glass')
        self.window.apply_preset('qqs-original')
        self.assertEqual(self.window.theme,appearance.MENU)
        self.assertTrue(self.window.theme['show_logo'])
        self.assertFalse(self.window.theme['glass_effect'])
        self.window.restore_previous_theme();self.assertTrue(self.window.theme['glass_effect'])
    def test_liquid_glass_alpha_render_and_restore(self):
        from PySide6.QtGui import QColor
        before=dict(self.window.theme)
        self.window.apply_preset('qqs-liquid-glass')
        theme=self.window.theme
        self.assertTrue(theme['glass_effect'])
        self.assertLess(QColor(theme['background']).alpha(),255)
        self.assertLess(QColor(theme['row_background']).alpha(),255)
        self.window.show();QAPP.processEvents()
        self.assertFalse(self.window.grab().isNull())
        self.window.restore_previous_theme();self.assertEqual(self.window.theme,before)
    def test_presets_restore_and_export_import_values(self):
        w=self.window;before=dict(w.theme);w.apply_preset('qqs-dark');self.assertEqual(w.theme['background'],'#171b26')
        w.restore_previous_theme();self.assertEqual(w.theme,before)
        exported=self.root/'export.rasi';appearance.write_theme(exported,w.theme)
        values=read_theme(exported,MENU);self.assertEqual(values,w.theme)
        with patch.object(app.QFileDialog,'getOpenFileName',return_value=(str(exported),'')):w.import_menu_theme()
        self.assertEqual(w.theme,before)
