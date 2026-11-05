"""Managed sessions survive the editor and can be recovered on reopen."""
import json
import os
import signal
import subprocess
import time
import tempfile
import sys
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def identity(pid):
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (OSError, ValueError, IndexError): return None


def launch_environment(base=None, home=None, data_dir=None):
    """Build every launch environment independently of interactive shell startup.

    Keep explicit paths first, remember existing custom module roots, and check
    conventional user Qt 6 locations again on each launch (including new installs).
    """
    env = dict(os.environ if base is None else base)
    home = Path.home() if home is None else Path(home)
    data = Path(env.get('XDG_DATA_HOME', str(home / '.local/share')))
    cache = Path(data_dir) / 'module-paths.json' if data_dir is not None else None
    remembered = []
    if cache is not None:
        try:
            value = json.loads(cache.read_text(encoding='utf-8'))
            stored = value.get('qml_import_paths', [])
            if isinstance(stored, list):
                remembered = [p for p in stored if isinstance(p, str) and Path(p).is_absolute()]
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    paths = []
    explicit = [part for part in env.get('QML_IMPORT_PATH', '').split(os.pathsep) if part]
    legacy = [part for part in env.get('QML2_IMPORT_PATH', '').split(os.pathsep) if part]
    candidates = [home / '.local/lib/qt6/qml', home / '.local/lib64/qt6/qml',
                  data / 'qt6/qml', Path('/usr/local/lib/qt6/qml'),
                  Path('/usr/local/lib64/qt6/qml')]
    seen = set()
    def add(path):
        path = str(path)
        key = str(Path(path).resolve())
        if key not in seen:
            seen.add(key); paths.append(path)
    for path in explicit:
        add(path)
    for path in legacy + remembered + [str(p) for p in candidates]:
        if Path(path).is_dir():
            add(path)
    if paths:
        env['QML_IMPORT_PATH'] = os.pathsep.join(paths)
    if cache is not None:
        saved = list(dict.fromkeys(remembered + [str(Path(p).resolve())
                     for p in explicit + legacy if Path(p).is_dir()]))
        write_json(cache, {'qml_import_paths': saved})
    return env


class Runtime:
    def __init__(self, data):
        self.data = Path(data); self.data.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data/'session.json'; self.log_path = self.data/'session.log'
        self.child = None; self.state = {}; self.deadline = None
        try: self.state = json.loads(self.state_path.read_text())
        except (OSError, ValueError): pass
    def alive(self):
        return bool(self.state.get('boot', Path('/proc/sys/kernel/random/boot_id').read_text().strip()) == Path('/proc/sys/kernel/random/boot_id').read_text().strip() and self.state.get('start') and identity(self.state.get('pid')) == self.state['start'])
    def start(self, binary, entry, remember=True):
        plan={'backend':'quickshell','command':[binary,'--no-color','--path',str(entry)],
              'cwd':str(Path(entry).parent),'environment':{},'ready_text':'Configuration Loaded','grace_ms':1200}
        self.start_plan(plan,entry,remember)
    def start_plan(self,plan,entry,remember=True):
        if self.alive():raise RuntimeError('A shell started by qqs is already running.')
        env=launch_environment(data_dir=self.data);env.update(plan.get('environment',{}))
        spec=self.data/'launch-plan.json';write_json(spec,plan)
        with self.log_path.open('wb') as log:
            log.write(('INFO: qqs QML module paths: '+env.get('QML_IMPORT_PATH','(Qt defaults)')+'\n').encode());log.flush()
            self.child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('shell_runner.py')),str(spec)],cwd=plan['cwd'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        self.state={'pid':self.child.pid,'start':identity(self.child.pid),'entry':str(entry),
                    'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'backend':plan['backend'],'group_owned':True}
        write_json(self.state_path,self.state)
        if remember:write_json(self.data/'last-interface.json',{'entry':str(entry),'backend':plan['backend'],'launch_options':{'windows':plan['eww_windows']} if 'eww_windows' in plan else {}})
        self.deadline=None
    def stop(self):
        if self.alive():
            try:
                if self.state.get('group_owned'):os.killpg(self.state['pid'],signal.SIGTERM)
                else:os.kill(self.state['pid'],signal.SIGTERM)
                self.deadline=time.monotonic()+2.5
            except ProcessLookupError:pass
    def poll(self):
        code=self.child.poll() if self.child else None
        if self.deadline and self.alive() and time.monotonic()>=self.deadline:
            try:
                if self.state.get('group_owned'):os.killpg(self.state['pid'],signal.SIGKILL)
                else:os.kill(self.state['pid'],signal.SIGKILL)
            except ProcessLookupError:pass
            self.deadline=None
        return code
    def text(self):
        try:
            with self.log_path.open('rb') as f:
                f.seek(0, 2); length=f.tell(); f.seek(max(0, length-100000))
                return f.read().decode('utf-8', errors='replace')
        except OSError: return ''
