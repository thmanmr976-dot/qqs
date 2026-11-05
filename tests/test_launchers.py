import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,json,tempfile,time,subprocess,signal,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backends import backend_for,discover_entries,launch_plan
from launchers import integrations,item_plan,prepare_bindings,dependency_report
from launcher_proxy import forwarded_arguments
from runtime import Runtime,identity
from core import extract_archive
from PySide6.QtWidgets import QApplication
import app,appearance
QAPP=QApplication.instance() or QApplication([])

class LauncherIntegrationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def file(self,name,text):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return p
    def stop(self,runtime):
        runtime.stop();end=time.monotonic()+4
        while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
        if runtime.child:runtime.child.wait(timeout=3)
    def test_import_launcher_only_repository_and_keep_shell_priority(self):
        archive=self.root/'rofi.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('theme/launcher.rasi','window { width: 500px; }')
        root=extract_archive(archive,self.root/'library');self.assertEqual(backend_for(discover_entries(root)[0]),'rofi')
        shell=root/'shell.qml';shell.write_text('import Quickshell')
        self.assertEqual(discover_entries(root),[shell])
    def test_rofi_wofi_and_launcher_script_commands(self):
        rofi=self.file('rofi/config.rasi','configuration { modi: "drun"; }')
        config=self.file('wofi/config','show=drun');self.file('wofi/style.css','#input { color: white; }')
        script=self.file('launch.sh','#!/bin/sh\nrofi -show drun')
        with patch('backends.shutil.which',side_effect=lambda name:'/usr/bin/'+name):
            rp=launch_plan(rofi);wp=launch_plan(config);sp=launch_plan(script)
        self.assertTrue(rp['transient']);self.assertIn('-config',rp['command'])
        self.assertTrue(wp['transient']);self.assertIn('--style',wp['command'])
        self.assertTrue(sp['transient']);self.assertEqual(backend_for(script),'launcher-script')
        config.rename(config.with_name('config.ini'))
        with patch('backends.shutil.which',return_value='/usr/bin/wofi'):
            stylesheet_plan=launch_plan(config.parent/'style.css')
        self.assertEqual(stylesheet_plan['command'][-2:],['--conf',str(config.with_name('config.ini'))])
    def test_project_rofi_plugins_are_forwarded_to_native_rofi(self):
        theme=self.file('rofi/config.rasi','configuration {}');self.file('rofi/plugins/example.so','placeholder')
        with patch('backends.shutil.which',return_value='/usr/bin/rofi'):plan=launch_plan(theme)
        self.assertEqual(plan['command'][-2:],['-plugin-path',str(theme.parent/'plugins')])
    def test_wrapper_preserves_mode_and_explicit_configuration(self):
        self.assertEqual(forwarded_arguments(['-dmenu','-p','Pick'],['-theme','rice.rasi']),['-theme','rice.rasi','-dmenu','-p','Pick'])
        self.assertEqual(forwarded_arguments(['-theme','mine.rasi'],['-theme','rice.rasi']),['-theme','mine.rasi'])
        self.assertEqual(forwarded_arguments(['--style=mine.css'],['--style','rice.css']),['--style=mine.css'])
        self.assertEqual(forwarded_arguments(['-no-config'],['-config','rice.rasi']),['-no-config'])
    def test_rice_local_wrapper_is_used_without_global_changes(self):
        entry=self.file('rice/shell.qml','import Quickshell');theme=self.file('rice/rofi/config.rasi','configuration {}')
        tool=self.file('native-rofi','#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))');tool.chmod(0o755)
        rice={'entry':str(entry),'root':str(entry.parent)}
        plan={'command':['unused'],'environment':{},'cwd':str(entry.parent)}
        before=os.environ.get('PATH')
        with patch('launchers.shutil.which',side_effect=lambda name:str(tool) if name=='rofi' else None):bound=prepare_bindings(rice,self.root/'data',plan)
        env=dict(os.environ,**bound['environment'])
        result=subprocess.run(['rofi','-dmenu'],env=env,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),['-config',str(theme),'-dmenu'])
        self.assertEqual(os.environ.get('PATH'),before)
    def test_any_named_launcher_profile_can_be_bound(self):
        self.file('project/menu/title.txt','CUSTOM_MENU')
        entry=self.file('project/qqs-shell.json',json.dumps({'command':['python3','main.py'],'launchers':[{'name':'Custom menu','bind_as':'my-menu','command':['python3','-c','print(open("title.txt").read())'],'working_directory':'menu'}]}))
        rice={'entry':str(entry),'root':str(entry.parent)}
        items=integrations(rice);self.assertEqual(items[0]['name'],'Custom menu')
        plan=prepare_bindings(rice,self.root/'data',{'environment':{}})
        result=subprocess.run(['my-menu'],env=dict(os.environ,**plan['environment']),capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),'CUSTOM_MENU')
    def test_cancelled_transient_does_not_report_failure(self):
        entry=self.file('cancel.py','raise SystemExit(1)');runtime=Runtime(self.root/'data')
        try:
            plan=launch_plan(entry);plan['transient']=True;runtime.start_plan(plan,str(entry),remember=False)
            end=time.monotonic()+3
            while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
            self.assertNotIn('QQS_ERROR',runtime.text());self.assertEqual(runtime.child.wait(timeout=2),0)
        finally:self.stop(runtime)
    def test_closing_launcher_preserves_the_application_it_started(self):
        pidfile=self.root/'application.pid'
        entry=self.file('launch.py','import subprocess,sys\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\nopen('+repr(str(pidfile))+',"w").write(str(p.pid))')
        runtime=Runtime(self.root/'data');application=None
        try:
            plan=launch_plan(entry);plan['transient']=True;runtime.start_plan(plan,str(entry),remember=False)
            end=time.monotonic()+4
            while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
            application=int(pidfile.read_text());self.assertIsNotNone(identity(application));self.assertNotIn('QQS_ERROR',runtime.text())
        finally:
            self.stop(runtime)
            if application and identity(application):os.kill(application,signal.SIGTERM)
    def test_transient_config_error_is_still_reported(self):
        entry=self.file('bad.py','import sys\nprint("ERROR: invalid launcher config",file=sys.stderr)\nraise SystemExit(1)')
        runtime=Runtime(self.root/'data')
        try:
            plan=launch_plan(entry);plan['transient']=True;runtime.start_plan(plan,str(entry),remember=False)
            end=time.monotonic()+3
            while runtime.alive() and time.monotonic()<end:runtime.poll();time.sleep(.03)
            self.assertIn('QQS_ERROR',runtime.text())
        finally:self.stop(runtime)
    def test_selecting_launcher_never_stops_or_replaces_desktop_shell(self):
        entry=self.file('theme.rasi','window { width: 500px; }')
        with patch.object(app,'DATA',self.root/'data'),patch.object(app,'CONFIG',self.root/'config'),patch.object(appearance,'CONFIG',self.root/'config'):
            w=app.Window();w.monitor.stop();w.rices=[{'name':'Rofi theme','entry':str(entry)}];w.refresh_list()
            try:
                with patch.object(w.runtime,'stop') as stop,patch.object(w,'run_launcher') as run,patch.dict(os.environ,{'WAYLAND_DISPLAY':'test'}),patch('backends.shutil.which',return_value='/usr/bin/rofi'):
                    w.select_rice(w.list.item(0));stop.assert_not_called();run.assert_called_once();self.assertTrue(run.call_args.args[0]['transient'])
                self.assertIsNone(w.loader)
            finally:w.theme_reload.stop();w.hide();w.deleteLater();QAPP.processEvents()

if __name__=='__main__':unittest.main()
