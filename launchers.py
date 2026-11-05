"""Rice-local launcher discovery, dependency reports and isolated PATH wrappers."""
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from runtime import write_json

COMMON=('rofi','wofi','fuzzel','tofi','bemenu','anyrun')
SKIP={'.git','node_modules','.venv','venv','__pycache__','build','target','dist'}


def integrations(rice):
    from backends import backend_for,TRANSIENT
    from library import rice_folder
    root=rice_folder(rice).resolve();items=[];visited=0
    if not root.is_dir():return items
    for directory,dirs,files in os.walk(root,followlinks=False):
        folder=Path(directory);dirs[:]=[name for name in dirs if name not in SKIP and not (folder/name).is_symlink()]
        if len(folder.relative_to(root).parts)>7:dirs[:]=[];continue
        visited+=len(files)
        if visited>12000:break
        for name in sorted(files):
            file=folder/name
            if file.is_symlink() or file.suffix not in ('.rasi','.css','.ini','.sh','') or not file.is_file():continue
            try:backend=backend_for(file)
            except ValueError:continue
            if backend in TRANSIENT:
                if file.suffix=='.rasi' and name not in ('config.rasi','theme.rasi','launcher.rasi'):
                    text=file.read_text(encoding='utf-8',errors='replace')[:200000]
                    if not re.search(r'(?:window|listview|inputbar|configuration)\s*\{|@theme',text):continue
                items.append({'name':backend.title()+' · '+str(file.relative_to(root)),'entry':str(file),'backend':backend})
    entry=Path(rice['entry'])
    profile=entry if entry.name=='qqs-shell.json' else root/'qqs-shell.json'
    if profile.is_file():
        value=json.loads(profile.read_text())
        declared=value.get('launchers',[])
        if not isinstance(declared,list):raise ValueError('launchers must be a list of launcher profiles.')
        for item in declared:
            if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip():raise ValueError('Each launcher profile needs a name and an argument-array command.')
            items.append({'name':item['name'],'profile':item,'base':str(profile.parent),'backend':'custom'})
    return items


def item_plan(item):
    from backends import launch_plan,executable
    if item.get('entry'):return launch_plan(item['entry'])
    value=item['profile'];command=value.get('command');working=value.get('working_directory','.')
    if not isinstance(working,str):raise ValueError('Launcher working_directory must be a path.')
    cwd=(Path(item['base'])/working).resolve()
    if not cwd.is_dir():raise ValueError('Launcher working directory not found: '+str(cwd))
    environment=value.get('environment',{})
    if not isinstance(environment,dict) or not all(isinstance(k,str) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',k) and isinstance(v,str) and '\x00' not in v for k,v in environment.items()):raise ValueError('Invalid launcher environment.')
    if not isinstance(command,list) or not command or not all(isinstance(v,str) and v and '\x00' not in v for v in command):raise ValueError('Launcher command must be an argument array.')
    return {'backend':'custom','command':[executable(command[0],cwd),*command[1:]],'cwd':str(cwd),'environment':environment,'ready_text':'','grace_ms':500,'transient':True,'require_window':True}


def launcher_dependencies(rice):
    from library import rice_folder
    root=rice_folder(rice);found=set();count=0
    if not root.is_dir():return []
    for directory,dirs,files in os.walk(root,followlinks=False):
        folder=Path(directory);dirs[:]=[name for name in dirs if name not in SKIP and not (folder/name).is_symlink()]
        if len(folder.relative_to(root).parts)>7:dirs[:]=[];continue
        for name in files:
            file=folder/name
            if file.suffix not in ('.qml','.sh','.js','.ts','.tsx','.py','.lua','.conf','.jsonc') or file.is_symlink() or file.stat().st_size>300000:continue
            count+=1
            if count>400:return sorted(found)
            text=file.read_text(encoding='utf-8',errors='replace')
            for command in COMMON:
                if re.search(r'(?<![\w./-])'+re.escape(command)+r'(?=[\s\"\x27,\]])',text):found.add(command)
    return sorted(found)


def dependency_report(rice):
    from backends import executable
    names=set(launcher_dependencies(rice));profiles={}
    for item in integrations(rice):
        if item['backend'] in COMMON:names.add(item['backend'])
        elif item.get('profile'):
            command=item['profile'].get('command')
            if isinstance(command,list) and command and isinstance(command[0],str):
                names.add(command[0]);profiles[command[0]]=item
    report=[]
    for name in sorted(names):
        resolved=shutil.which(name)
        if name in profiles:
            item=profiles[name];working=item['profile'].get('working_directory','.')
            if isinstance(working,str):
                try:resolved=executable(name,(Path(item['base'])/working).resolve())
                except ValueError:resolved=None
        report.append((name,resolved))
    return report


def prepare_bindings(rice,data,plan):
    """Scope discovered configs to subprocesses of this rice, never global config."""
    selected={}
    for item in integrations(rice):
        name=item['backend']
        if name not in ('rofi','wofi','fuzzel','tofi') or not shutil.which(name):continue
        current=selected.get(name)
        rank=0 if Path(item['entry']).name in ('config','config.rasi','fuzzel.ini') else 1
        if current is None or rank<current[0]:selected[name]=(rank,item)
    custom=[item for item in integrations(rice) if item.get('profile',{}).get('bind_as')]
    if not selected and not custom:return plan
    key=hashlib.sha256(rice['entry'].encode()).hexdigest()[:16]
    folder=Path(data)/'launcher-bindings'/key;binary_folder=folder/'bin';binary_folder.mkdir(parents=True,exist_ok=True)
    bindings={}
    for name,(_,item) in selected.items():
        native_plan=item_plan(item);native=native_plan['command'];arguments=native[1:]
        # Configuration forwarding must not override a caller's requested mode.
        if name=='rofi' and '-show' in arguments:
            index=arguments.index('-show');del arguments[index:index+2]
        if name=='wofi' and '--show' in arguments:
            index=arguments.index('--show');del arguments[index:index+2]
        bindings[name]={'binary':native[0],'arguments':arguments,'cwd':native_plan['cwd']}
        wrapper=binary_folder/name
        wrapper.write_text('#!'+sys.executable+'\nimport os,sys\nos.execv('+repr(sys.executable)+', ['+repr(sys.executable)+','+repr(str(Path(__file__).with_name('launcher_proxy.py')))+','+repr(name)+', *sys.argv[1:]])\n')
        wrapper.chmod(0o755)
    for item in custom:
        alias=item['profile']['bind_as']
        if not isinstance(alias,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9-]*',alias):raise ValueError('Launcher bind_as must be a simple executable name.')
        custom_plan=item_plan(item);native=custom_plan['command'];bindings[alias]={'binary':native[0],'arguments':native[1:],'forward_options':False,'environment':custom_plan['environment'],'cwd':custom_plan['cwd']}
        wrapper=binary_folder/alias
        wrapper.write_text('#!'+sys.executable+'\nimport os,sys\nos.execv('+repr(sys.executable)+', ['+repr(sys.executable)+','+repr(str(Path(__file__).with_name('launcher_proxy.py')))+','+repr(alias)+', *sys.argv[1:]])\n')
        wrapper.chmod(0o755)
    spec=folder/'bindings.json';write_json(spec,bindings)
    env=dict(plan.get('environment',{}));env['PATH']=str(binary_folder)+os.pathsep+env.get('PATH',os.environ.get('PATH',''));env['QQS_LAUNCHER_BINDINGS']=str(spec)
    return {**plan,'environment':env}
