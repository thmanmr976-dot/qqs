"""Login restoration for XDG desktops and Hyprland Lua configurations."""
import fcntl
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path
from runtime import Runtime, write_json
from backends import launch_plan,backend_for
from launchers import integrations,prepare_bindings

START = '-- qqs login restore: begin'
END = '-- qqs login restore: end'

def configure(enabled, data):
    write_json(Path(data)/'login-restore.json', {'enabled': bool(enabled)})
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    desktop = config/'autostart/qqs.desktop'
    script = Path(__file__).resolve()
    command = shlex.join([sys.executable, str(script), '--restore', str(data)])
    if enabled:
        desktop.parent.mkdir(parents=True, exist_ok=True)
        def desktop_quote(value):
            value = str(value).replace('%', '%%')
            for char in ('\\', '"', '`', '$'): value = value.replace(char, '\\'+char)
            return '"'+value+'"'
        desktop.write_text('[Desktop Entry]\nType=Application\nName=qqs — Restore interface\nComment=Restore the last qqs interface at login\nExec='+ ' '.join(desktop_quote(v) for v in [sys.executable, script, '--restore', data])+'\nTerminal=false\n', encoding='utf-8')
    else: desktop.unlink(missing_ok=True)
    # Plain Hyprland sessions do not necessarily launch XDG autostart entries.
    lua = config/'hypr/hyprland.lua'
    if lua.is_file():
        source = lua.read_text()
        if START in source and END in source:
            a=source.index(START); b=source.index(END,a)+len(END)
            source=source[:a]+source[b:]
        if enabled:
            source=source.rstrip()+'\n\n'+START+'\nhl.on("hyprland.start", function()\n    hl.exec_cmd('+json.dumps(command)+')\nend)\n'+END+'\n'
        if source != lua.read_text():
            if not lua.with_suffix('.lua.qqs-backup').exists(): shutil.copy2(lua,lua.with_suffix('.lua.qqs-backup'))
            lua.write_text(source)

def restore(data):
    data=Path(data); data.mkdir(parents=True, exist_ok=True)
    with (data/'restore.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        flag=data/'login-restore.json'
        if flag.exists():
            enabled=json.loads(flag.read_text()).get('enabled', False)
        else:
            enabled=json.loads((data/'preferences.json').read_text()).get('restore_login', False)
        if not enabled: return
        runtime=Runtime(data)
        if runtime.alive(): return
        saved=data/'last-interface.json'
        record=json.loads(saved.read_text()) if saved.exists() else runtime.state
        entry=record.get('entry')
        if not entry: return
        if not Path(entry).is_file(): raise FileNotFoundError('Saved interface is missing: '+entry)
        for _ in range(30):
            display=os.environ.get('WAYLAND_DISPLAY','')
            if display and (Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))/display).exists(): break
            time.sleep(1)
        else: raise RuntimeError('No Wayland display available for login restoration.')
        options=record.get('launch_options',{})
        rice={'entry':entry,'root':str(Path(entry).parent)}
        try:
            preferences=json.loads((data/'preferences.json').read_text())
            rice=next((item for item in preferences.get('rices',[]) if item['entry']==entry),rice)
        except (OSError,ValueError):pass
        has_bindings=bool(integrations(rice))
        if backend_for(entry)=='quickshell' and not has_bindings:
            binary=shutil.which('quickshell') or shutil.which('qs')
            if not binary:raise RuntimeError('Quickshell is not installed.')
            runtime.start(binary,entry)
        else:
            plan=prepare_bindings(rice,data,launch_plan(entry,options))
            if not plan.get('transient'):runtime.start_plan(plan,entry)

if __name__=='__main__':
    data=Path(sys.argv[2])
    try: restore(data)
    except Exception as e:
        data.mkdir(parents=True, exist_ok=True)
        with (data/'session.log').open('a') as log: log.write('\nqqs login restore error: '+str(e)+'\n')
        sys.exit(1)
