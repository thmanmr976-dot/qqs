import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from startup import configure, restore
from runtime import write_json

class StartupTests(unittest.TestCase):
    def test_install_disable_and_keep_original_config(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'XDG_CONFIG_HOME':d}):
            p=Path(d)/'hypr/hyprland.lua'; p.parent.mkdir(); p.write_text('-- existing config\n')
            configure(True,Path(d)/'data'); configure(True,Path(d)/'data')
            self.assertEqual(p.read_text().count('-- qqs login restore: begin'),1)
            self.assertTrue((Path(d)/'autostart/qqs.desktop').exists())
            configure(False,Path(d)/'data')
            self.assertNotIn('hl.exec_cmd',p.read_text()); self.assertIn('-- existing config',p.read_text())
            self.assertFalse((Path(d)/'autostart/qqs.desktop').exists())
    def test_restore_uses_saved_entry_without_opening_editor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); entry=root/'shell.qml'; entry.write_text('')
            write_json(root/'preferences.json', {'restore_login':True})
            write_json(root/'last-interface.json', {'entry':str(entry)})
            (root/'wayland-test').touch()
            with patch.dict(os.environ, {'WAYLAND_DISPLAY':'wayland-test','XDG_RUNTIME_DIR':d}), patch('startup.Runtime') as runtime, patch('startup.shutil.which',return_value='/usr/bin/quickshell'):
                runtime.return_value.alive.return_value=False
                restore(root)
                runtime.return_value.start.assert_called_once_with('/usr/bin/quickshell',str(entry))
                runtime.return_value.start.reset_mock(); runtime.return_value.alive.return_value=True
                restore(root); runtime.return_value.start.assert_not_called()
