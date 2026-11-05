import os
import sys
import json
import time
import tempfile
import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backends import backend_for,discover_entries,launch_plan,eww_windows
from core import extract_archive
from runtime import Runtime,write_json,identity
from startup import restore

class BackendTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def file(self,name,text):
        file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text);return file
    def test_detect_all_frameworks_and_skip_unrelated_files(self):
        files=[self.file('qs/shell.qml','import Quickshell'),self.file('ags/app.tsx','import app from "ags/gtk4/app"'),self.file('old/config.js','import Widget from "resource:///com/github/Aylur/ags/widget.js"'),self.file('eww/eww.yuck','(defwindow bar [])'),self.file('waybar/config.jsonc','{"modules-left":["clock"]}')]
        self.file('node_modules/demo/shell.qml','import Quickshell')
        self.assertEqual([backend_for(f) for f in files],['quickshell','ags','ags-v1','eww','waybar'])
        found=discover_entries(self.root);self.assertEqual(set(found),set(files))
        unrelated=self.file('web/app.tsx','import React from "react"')
        with self.assertRaises(ValueError):backend_for(unrelated)
    def test_native_astal_fabric_and_compiled_archive(self):
        astal=self.file('astal/main.py','import gi\ngi.require_version("Astal", "3.0")')
        fabric=self.file('fabric/config.py','from fabric import Application')
        gjs=self.file('gjs/main.js','import Astal from "gi://Astal?version=3.0"')
        self.assertEqual(backend_for(astal),'astal-python');self.assertEqual(backend_for(fabric),'fabric');self.assertEqual(backend_for(gjs),'astal-gjs')
        with patch('backends.shutil.which',side_effect=lambda name:'/usr/bin/'+name):
            self.assertEqual(launch_plan(gjs)['command'][1],'-m')
        archive=self.root/'binary.zip'
        info=zipfile.ZipInfo('native/my-shell');info.external_attr=(0o100755<<16)
        with zipfile.ZipFile(archive,'w') as z:z.writestr(info,b'\x7fELF'+b'placeholder')
        imported=extract_archive(archive,self.root/'library')
        entry=discover_entries(imported)[0];self.assertTrue(os.access(entry,os.X_OK));self.assertEqual(backend_for(entry),'custom')
    def test_each_backend_builds_its_own_arguments(self):
        modern=self.file('modern/app.ts','import app from "astal/gtk3/app"')
        legacy=self.file('legacy/config.js','import "resource:///com/github/Aylur/ags/app.js"')
        config=self.file('waybar/config.jsonc','{"modules-left":["clock"]}');self.file('waybar/style.css','* {}')
        with patch('backends.shutil.which',side_effect=lambda name:'/usr/bin/'+name):
            self.assertEqual(launch_plan(modern)['command'][1:],['run',str(modern)])
            self.assertEqual(launch_plan(legacy)['command'][1:],['--config',str(legacy)])
            self.assertEqual(launch_plan(config)['command'][1:],['--config',str(config),'--style',str(config.parent/'style.css')])
    def test_eww_includes_and_selected_windows(self):
        config=self.file('eww/eww.yuck','; (defwindow ignored [])\n(include "bar.yuck")\n(defwindow launcher [])')
        self.file('eww/bar.yuck','(defwindow bar [] "(defwindow fake)")')
        self.assertEqual(eww_windows(config),['launcher','bar'])
        with patch('backends.shutil.which',return_value='/usr/bin/eww'):
            plan=launch_plan(config,{'windows':['bar']})
        self.assertIn('--no-daemonize',plan['command']);self.assertEqual(plan['eww_windows'],['bar'])
    def test_non_qml_archives_and_entry_priority(self):
        for filename,text in [('app.tsx','import app from "ags/gtk4/app"'),('eww.yuck','(defwindow bar [])'),('config.jsonc','{"modules-left":[]}'),('launch.sh','#!/bin/sh\nsleep 30')]:
            with self.subTest(file=filename):
                archive=self.root/'shell.zip'
                with zipfile.ZipFile(archive,'w') as z:z.writestr('repo/'+filename,text)
                extracted=extract_archive(archive,self.root/'library');self.assertTrue(discover_entries(extracted))
        folder=self.root/'custom';folder.mkdir();(folder/'qqs-shell.json').write_text('{"command":["shell"]}');(folder/'shell.qml').write_text('')
        self.assertEqual(discover_entries(folder),[folder/'qqs-shell.json'])
    def test_manifest_arguments_and_working_directory_are_not_shell_code(self):
        self.file('project/config/.keep','');entry=self.file('project/qqs-shell.json',json.dumps({'command':['python3','app.py','literal;echo no'],'working_directory':'config','ready_text':'READY','environment':{'SHELL_THEME':'blue'}}))
        plan=launch_plan(entry);self.assertEqual(plan['command'][-1],'literal;echo no');self.assertEqual(plan['cwd'],str(entry.parent/'config'));self.assertEqual(plan['environment'],{'SHELL_THEME':'blue'})
        entry.write_text('{"command":"python3 app.py"}')
        with self.assertRaisesRegex(ValueError,'array'):launch_plan(entry)
    def test_missing_runtime_reports_before_launch(self):
        entry=self.file('app.ts','import app from "ags/gtk4/app"')
        with patch('backends.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'ags'):launch_plan(entry)
    def stop(self,runtime):
        runtime.stop()
        end=time.monotonic()+4
        while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
        if runtime.child:runtime.child.wait(timeout=3)
    def wait_ready(self,runtime):
        end=time.monotonic()+4
        while time.monotonic()<end:
            runtime.poll()
            if 'QQS_READY' in runtime.text():return
            if not runtime.alive():break
            time.sleep(.03)
        self.fail(runtime.text())
    def test_supervisor_tracks_background_children_and_does_not_stop_external_process(self):
        capture=self.root/'child.pid'
        entry=self.file('launch.py','import subprocess,sys\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\nopen('+repr(str(capture))+',"w").write(str(p.pid))\n')
        runtime=Runtime(self.root/'data');outside=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        try:
            plan=launch_plan(entry);plan['grace_ms']=100;runtime.start_plan(plan,str(entry));self.wait_ready(runtime)
            child_pid=int(capture.read_text());self.assertIsNotNone(identity(child_pid))
            recovered=Runtime(runtime.data);self.assertTrue(recovered.alive());recovered.stop()
            self.stop(runtime);self.assertIsNone(identity(child_pid));self.assertIsNone(outside.poll())
        finally:
            self.stop(runtime);outside.terminate();outside.wait(timeout=3)
    def test_foreground_exit_does_not_report_success(self):
        entry=self.file('exits.py','print("finished")');runtime=Runtime(self.root/'data')
        try:
            runtime.start_plan(launch_plan(entry),str(entry))
            end=time.monotonic()+3
            while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
            self.assertIn('QQS_ERROR:',runtime.text());self.assertNotIn('QQS_READY',runtime.text())
        finally:self.stop(runtime)
    def test_eww_daemon_is_owned_and_windows_are_opened(self):
        script=self.file('eww-tool','#!/usr/bin/python3\nimport sys,time,pathlib\np=pathlib.Path(sys.argv[sys.argv.index("--config")+1])\nif "ping" in sys.argv:sys.exit(0 if (p/"alive").exists() else 1)\nif "open-many" in sys.argv:\n (p/"opened").write_text(" ".join(sys.argv[sys.argv.index("open-many")+1:]));sys.exit(0)\n(p/"alive").touch()\nwhile True:time.sleep(.1)\n');script.chmod(0o755)
        entry=self.file('eww/eww.yuck','(defwindow bar [])');runtime=Runtime(self.root/'data')
        try:
            with patch('backends.shutil.which',return_value=str(script)):plan=launch_plan(entry,{'windows':['bar']})
            runtime.start_plan(plan,str(entry));self.wait_ready(runtime)
            self.assertEqual((entry.parent/'opened').read_text(),'bar')
        finally:self.stop(runtime)
    def test_desktop_entry_uses_its_directory_and_arguments(self):
        directory=self.root/'work';directory.mkdir()
        entry=self.file('shell.desktop','[Desktop Entry]\nType=Application\nName=My Shell\nPath='+str(directory)+'\nIcon=shell-icon\nExec=python3 app.py %c %k %i %U %%\n')
        plan=launch_plan(entry)
        self.assertEqual(plan['cwd'],str(directory))
        self.assertEqual(plan['command'][1:],['app.py','My Shell',str(entry),'--icon','shell-icon','%'])
    def test_login_restore_rebuilds_non_quickshell_launch_plan(self):
        entry=self.file('waybar/config.jsonc','{"modules-left":[]}');data=self.root/'data'
        write_json(data/'login-restore.json',{'enabled':True});write_json(data/'last-interface.json',{'entry':str(entry)})
        (self.root/'wayland-test').touch()
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'wayland-test','XDG_RUNTIME_DIR':str(self.root)}),patch('startup.Runtime') as runtime,patch('backends.shutil.which',return_value='/usr/bin/waybar'):
            runtime.return_value.alive.return_value=False;restore(data)
            runtime.return_value.start.assert_not_called()
            self.assertEqual(runtime.return_value.start_plan.call_args.args[0]['backend'],'waybar')

if __name__=='__main__':unittest.main()
