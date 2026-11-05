#!/usr/bin/env python3
"""Install a per-user app menu entry and the default Hyprland shortcut."""
import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from runtime import launch_environment
from bundled_rices import install_bundled

BASE=Path(__file__).resolve().parent

def desktop_quote(value):
    value=str(value).replace('%','%%')
    for c in ('\\','"','`','$'): value=value.replace(c,'\\'+c)
    return '"'+value+'"'

def install():
    config=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    data=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))
    bundled_count=install_bundled(data/'quickshell-studio')
    launch_environment(data_dir=data/'quickshell-studio')
    apps=data/'applications'; apps.mkdir(parents=True,exist_ok=True)
    command=shlex.join([sys.executable,str(BASE/'app.py')])
    desktop=apps/'qqs.desktop'
    desktop.write_text('[Desktop Entry]\nType=Application\nName=qqs\nGenericName=Quick Quick Shell\nComment=Switch your Quickshell rice\nExec='+ ' '.join(desktop_quote(x) for x in [sys.executable,BASE/'app.py'])+'\nIcon='+str(BASE/'assets/logo.png')+'\nTerminal=false\nCategories=Utility;Settings;\nStartupWMClass=qqs\n',encoding='utf-8')
    lua=config/'hypr/hyprland.lua'; conf=config/'hypr/hyprland.conf'
    start='-- qqs launcher shortcut: begin'; end='-- qqs launcher shortcut: end'
    if lua.exists():
        path=lua; block=start+'\nhl.bind("CTRL + SHIFT + Q", hl.dsp.exec_cmd('+json.dumps(command)+'))\n'+end
    elif conf.exists():
        path=conf; start='# qqs launcher shortcut: begin'; end='# qqs launcher shortcut: end'
        block=start+'\nbind = CTRL SHIFT, Q, exec, '+command+'\n'+end
    else: return f'Application menu entry installed; {bundled_count} bundled rices added. No Hyprland config was found; shortcut was not installed.'
    source=path.read_text()
    if start in source and end in source:
        a=source.index(start); b=source.index(end,a)+len(end); source=source[:a]+source[b:]
    new=source.rstrip()+'\n\n'+block+'\n'
    if new!=path.read_text():
        backup=path.with_name(path.name+'.qqs-shortcut-backup')
        if not backup.exists(): shutil.copy2(path,backup)
        path.write_text(new)
    rule_start='-- qqs popup window: begin' if path.suffix=='.lua' else '# qqs popup window: begin'
    rule_end=rule_start.replace('begin','end')
    content=path.read_text()
    if rule_start in content and rule_end in content:
        a=content.index(rule_start);b=content.index(rule_end,a)+len(rule_end);content=content[:a]+content[b:]
    if path.suffix=='.lua':
        rule='hl.window_rule({ name = "qqs-popup", match = { title = "^qqs — Quick Quick Shell$" }, float = true, center = true, pin = true })'
    else:
        rule='\n'.join('windowrulev2 = '+effect+',title:^(qqs — Quick Quick Shell)$' for effect in ('float','center','pin'))
    content=content.rstrip()+'\n\n'+rule_start+'\n'+rule+'\n'+rule_end+'\n'
    if content!=path.read_text():path.write_text(content)
    return f'Installed qqs with {bundled_count} bundled rices and configured Ctrl+Shift+Q in '+str(path)

if __name__=='__main__': print(install())
