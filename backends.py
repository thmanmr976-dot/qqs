"""Detect shell entry points and build explicit, shell-free launch plans."""
import json
import os
import re
import shlex
import shutil
from pathlib import Path

NAMES={'quickshell':'Quickshell','ags':'AGS / Astal','ags-v1':'AGS v1','eww':'Eww','waybar':'Waybar','fabric':'Fabric (Python)','astal-python':'Astal (Python)','astal-gjs':'Astal (GJS)','launcher-script':'Launcher script','rofi':'Rofi launcher','wofi':'Wofi launcher','fuzzel':'Fuzzel launcher','tofi':'Tofi launcher','custom':'Custom launcher'}
SKIP={'.git','node_modules','.venv','venv','__pycache__','target','build','dist'}
SCRIPTS=('launch.sh','start.sh','run.sh')
TRANSIENT={'rofi','wofi','fuzzel','tofi','launcher-script'}


def small_text(path):
    if path.stat().st_size>1024*1024: return ''
    return path.read_text(encoding='utf-8',errors='replace')


def backend_for(path):
    path=Path(path)
    if not path.is_file(): raise ValueError('Shell entry file not found: '+str(path))
    name=path.name;ext=path.suffix.lower()
    if name=='qqs-shell.json': return 'custom'
    if ext=='.rasi':return 'rofi'
    if ext=='.sh':
        text='\n'.join(line for line in small_text(path).splitlines() if not line.lstrip().startswith('#'))
        if re.search(r'\b(?:rofi|wofi|fuzzel|tofi|bemenu|anyrun)\b',text) and not re.search(r'\b(?:quickshell|qs|ags|eww|waybar|hyprpanel|dms)\b',text):return 'launcher-script'
    if name=='fuzzel.ini':return 'fuzzel'
    if name=='config' and path.parent.name=='tofi':return 'tofi'
    if name in ('config','config.ini') and path.parent.name=='wofi':return 'wofi'
    if ext=='.css' and (path.parent.name=='wofi' or re.search(r'#(?:input|outer-box|inner-box|entry)\b',small_text(path)) and not re.search(r'QWidget|QLineEdit|QPushButton',small_text(path))):return 'wofi'
    if ext=='.qml': return 'quickshell'
    if name=='eww.yuck': return 'eww'
    if ext=='.py':
        text=small_text(path)
        if re.search(r'(?:from|import)\s+fabric\b',text):return 'fabric'
        if 'Astal' in text and ('gi.repository' in text or 'gi.require_version' in text):return 'astal-python'
    if ext in ('.ts','.tsx','.js','.jsx'):
        text=small_text(path)
        if 'resource:///com/github/Aylur/ags' in text: return 'ags-v1'
        if ext=='.js' and 'gi://Astal' in text and not any(token in text for token in ('ags/','astal/')):return 'astal-gjs'
        if re.search(r'[\"\'](?:ags(?:/|[\"\'])|astal(?:/|[\"\'])|gi://Astal)',text): return 'ags'
    if name in ('config','config.jsonc','config.json'):
        text=small_text(path)
        if re.search(r'"modules-(?:left|center|right)"\s*:',text) or path.parent.name=='waybar':return 'waybar'
    if ext in ('.sh','.py','.desktop') or os.access(path,os.X_OK): return 'custom'
    raise ValueError('Unrecognized shell entry. Select its launch script/executable, or add a qqs-shell.json launch profile.')


def discover_entries(root):
    root=Path(root).resolve()
    if root.is_file():backend_for(root);return [root]
    found=[];qml=[];count=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        folder=Path(directory);dirs[:]=sorted(d for d in dirs if d not in SKIP and not (folder/d).is_symlink())
        if len(folder.relative_to(root).parts)>10:dirs[:]=[];continue
        count+=len(files)
        if count>20000:raise ValueError('Too many files to scan. Select the shell configuration folder directly.')
        if 'qqs-shell.json' in files:
            found.append(folder/'qqs-shell.json');dirs[:]=[];continue
        wrapper=next((name for name in SCRIPTS if name in files),None)
        if wrapper:
            found.append(folder/wrapper)
            if backend_for(folder/wrapper)!='launcher-script':dirs[:]=[];continue
        for name in sorted(files):
            path=folder/name
            if path.is_symlink():continue
            if path.suffix=='.qml':qml.append(path)
            if len(folder.relative_to(root).parts)<=1 and os.access(path,os.X_OK) and path.suffix in ('','.AppImage'):
                with path.open('rb') as file:header=file.read(4)
                if header==b'\x7fELF':found.append(path)
            if path.suffix=='.rasi' and (name in ('config.rasi','theme.rasi','launcher.rasi') or re.search(r'(?:window|listview|inputbar|configuration)\s*\{|@theme',small_text(path))):found.append(path);continue
            if path.suffix=='.css':
                try:
                    if backend_for(path)=='wofi':found.append(path);continue
                except ValueError:pass
            if name in ('fuzzel.ini','config.ini'):
                try:backend_for(path);found.append(path);continue
                except ValueError:pass
            if name=='shell.qml' or name=='eww.yuck' or name in ('app.ts','app.tsx','app.js','main.ts','main.tsx','main.js','index.ts','index.tsx','config.ts','config.tsx','config.js','main.py','app.py','config.py','config','config.json','config.jsonc'):
                try:kind=backend_for(path)
                except ValueError:continue
                if path.suffix=='.py' and kind=='custom':continue
                found.append(path)
    if not found:
        if len(qml)==1:return qml
        if len(qml)>1:raise ValueError('Several QML files found without shell.qml. Select the exact entry file.')
        raise ValueError('No supported shell or launcher entry found. Choose a Quickshell, AGS/Astal, Eww or Waybar configuration, a Rofi/Wofi theme, a launch script, or qqs-shell.json.')
    persistent=[path for path in found if backend_for(path) not in TRANSIENT]
    if persistent:found=persistent
    return sorted(set(found),key=lambda path:(len(path.relative_to(root).parts),str(path)))


def executable(command,cwd):
    if '/' in command:
        path=Path(command).expanduser();path=path if path.is_absolute() else cwd/path
        if path.is_file() and os.access(path,os.X_OK):return str(path.resolve())
    else:
        result=shutil.which(command)
        if result:return result
    raise ValueError('Required runtime or launcher is not installed/executable: '+command+'. Install the shell dependencies described in its README.')


def eww_windows(entry,seen=None):
    entry=Path(entry).resolve();seen=set() if seen is None else seen
    if entry in seen or len(seen)>12:return []
    seen.add(entry);text=small_text(entry)
    # Ignore comments and strings when collecting declared window names.
    tokens=re.sub(r'"(?:\\.|[^"\\])*"|;[^\n]*',lambda m:' ' if m.group(0).startswith(('"',';')) else m.group(0),text)
    windows=re.findall(r'\(defwindow\s+([\w-]+)',tokens)
    for include in re.findall(r'\(include\s+"([^"\n]+)"\s*\)',text):
        child=(entry.parent/include).resolve()
        if child.is_file():windows.extend(eww_windows(child,seen))
    return list(dict.fromkeys(windows))


def launch_plan(entry,options=None,quickshell=None):
    entry=Path(entry).expanduser().resolve();options=options or {};backend=backend_for(entry);cwd=entry.parent
    plan={'backend':backend,'cwd':str(cwd),'environment':{},'ready_text':'','grace_ms':1200}
    if backend=='quickshell':
        binary=quickshell or shutil.which('quickshell') or shutil.which('qs')
        if not binary:raise ValueError('Quickshell is not installed.')
        plan.update(command=[binary,'--no-color','--path',str(entry)],ready_text='Configuration Loaded')
    elif backend in ('ags','ags-v1'):
        binary=executable('ags',cwd)
        plan['command']=[binary,'run',str(entry)] if backend=='ags' else [binary,'--config',str(entry)]
        plan['require_window']=True
    elif backend in ('fabric','astal-python'):
        plan.update(command=[executable('python3',cwd),str(entry)],require_window=True)
    elif backend=='astal-gjs':
        plan.update(command=[executable('gjs',cwd),'-m',str(entry)],require_window=True)
    elif backend=='rofi':
        plan.update(command=[executable('rofi',cwd),'-show',options.get('mode','drun'),'-config' if entry.name=='config.rasi' else '-theme',str(entry)],transient=True,require_window=True)
        plugins=cwd/'plugins'
        if plugins.is_dir() and any(plugins.glob('*.so')):plan['command']+=['-plugin-path',str(plugins)]
    elif backend=='wofi':
        command=[executable('wofi',cwd),'--show',options.get('mode','drun')]
        if entry.suffix=='.css':
            command+=['--style',str(entry)]
            config=next((cwd/name for name in ('config','config.ini') if (cwd/name).is_file()),None)
            if config:command+=['--conf',str(config)]
        else:
            command+=['--conf',str(entry)]
            if (cwd/'style.css').is_file():command+=['--style',str(cwd/'style.css')]
        plan.update(command=command,transient=True,require_window=True)
    elif backend in ('fuzzel','tofi'):
        plan.update(command=[executable(backend,cwd),'--config',str(entry)],transient=True,require_window=True)
    elif backend=='waybar':
        plan['command']=[executable('waybar',cwd),'--config',str(entry)];plan['require_window']=True
        if (cwd/'style.css').is_file():plan['command']+=['--style',str(cwd/'style.css')]
    elif backend=='eww':
        windows=options.get('windows') or eww_windows(entry)
        if not windows:raise ValueError('No Eww windows found. Add defwindow declarations or use a custom launch profile.')
        if not isinstance(windows,list) or not all(isinstance(w,str) and re.fullmatch(r'[\w-]+',w) for w in windows):raise ValueError('Invalid Eww window names.')
        plan.update(command=[executable('eww',cwd),'--config',str(cwd),'--force-wayland','--no-daemonize','daemon'],eww_windows=windows,eww_config=str(cwd))
    elif entry.name=='qqs-shell.json':
        value=json.loads(entry.read_text(encoding='utf-8'))
        if not isinstance(value,dict):raise ValueError('qqs-shell.json must contain a JSON object.')
        command=value.get('command');work=value.get('working_directory','.')
        if not isinstance(work,str):raise ValueError('working_directory must be a path.')
        cwd=(entry.parent/work).resolve()
        if not cwd.is_dir():raise ValueError('Launch working directory not found: '+str(cwd))
        if not isinstance(command,list) or not command or not all(isinstance(v,str) and v and '\x00' not in v for v in command):raise ValueError('command must be a non-empty array of arguments, not a shell string.')
        env=value.get('environment',{})
        if not isinstance(env,dict) or not all(isinstance(k,str) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',k) and isinstance(v,str) and '\x00' not in v for k,v in env.items()):raise ValueError('environment must contain string environment variables.')
        ready=value.get('ready_text','');grace=value.get('startup_grace_ms',1200);surface=value.get('require_window',False)
        if not isinstance(surface,bool):raise ValueError('require_window must be true or false.')
        if not isinstance(ready,str) or type(grace) is not int or not 0<=grace<=60000:raise ValueError('Invalid ready_text or startup_grace_ms.')
        transient=value.get('transient',False)
        if not isinstance(transient,bool):raise ValueError('transient must be true or false.')
        required=value.get('requires',[])
        if not isinstance(required,list):raise ValueError('requires must be a list of executable names.')
        for dependency in required:
            if not isinstance(dependency,str):raise ValueError('requires must be a list of executable names.')
            executable(dependency,cwd)
        plan.update(command=[executable(command[0],cwd),*command[1:]],cwd=str(cwd),environment=env,ready_text=ready,grace_ms=grace,require_window=surface,transient=transient)
    elif entry.suffix=='.desktop':
        import configparser
        config=configparser.ConfigParser(interpolation=None);config.read(entry)
        raw=config.get('Desktop Entry','Exec',fallback='');command=[]
        desktop_path=config.get('Desktop Entry','Path',fallback='')
        if desktop_path:
            cwd=Path(desktop_path).expanduser()
            if not cwd.is_absolute():cwd=(entry.parent/cwd).resolve()
            if not cwd.is_dir():raise ValueError('Desktop launcher working directory does not exist: '+str(cwd))
        for token in shlex.split(raw):
            if token in ('%f','%F','%u','%U'):continue
            if token=='%i':
                icon=config.get('Desktop Entry','Icon',fallback='')
                if icon:command.extend(['--icon',icon])
                continue
            token=token.replace('%%','\x01').replace('%c',config.get('Desktop Entry','Name',fallback=entry.stem)).replace('%k',str(entry))
            if re.search(r'%[A-Za-z]',token):raise ValueError('Unsupported desktop Exec field. Use qqs-shell.json with explicit arguments.')
            command.append(token.replace('\x01','%'))
        if not command:raise ValueError('Desktop launcher has no executable command.')
        plan.update(command=[executable(command[0],cwd),*command[1:]],cwd=str(cwd))
    elif entry.suffix=='.py':plan['command']=[executable('python3',cwd),str(entry)]
    elif entry.suffix=='.sh':
        first=small_text(entry).splitlines()[0] if entry.stat().st_size else ''
        interpreter=shlex.split(first[2:]) if first.startswith('#!') else ['bash']
        plan['command']=[executable(interpreter[0],cwd),*interpreter[1:],str(entry)]
    else:plan['command']=[executable(str(entry),cwd)]
    if backend=='launcher-script':plan.update(transient=True,require_window=True)
    return plan
