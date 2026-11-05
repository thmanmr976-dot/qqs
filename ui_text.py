"""Action labels and instructions derived from the action they describe."""
from pathlib import Path
import re
from PySide6.QtGui import QKeySequence


def source_action(rice):
    if not rice.get('source'):
        return 'Import source unavailable'
    if rice.get('source_kind') == 'github':
        return 'Open import page on GitHub'
    if rice.get('source_kind') == 'zip':
        return 'Open original ZIP archive'
    path=Path(rice['source'])
    return 'Open original entry file' if path.is_file() or path.suffix.lower() in ('.qml','.yuck','.ts','.tsx','.js','.py','.sh','.json','.jsonc','.desktop') else 'Open original folder'


def is_import_input(text):
    text=text.strip()
    return bool(text and (text.startswith(('https://','http://','/','~','file://','.')) or text.endswith(('.zip','.qml','.yuck','.ts','.tsx','.js','.py','.sh','.json','.jsonc','.desktop')) or Path(text).expanduser().exists()))


def shortcut_hint(theme, text=''):
    def key(name):
        first=re.split(r'[;,]',theme[name])[0].strip().replace('Control+','Ctrl+')
        return QKeySequence(first).toString(QKeySequence.SequenceFormat.NativeText).replace('Return','Enter')
    action='import source' if is_import_input(text) else 'start selected rice'
    return f"{key('keys_accept')}: {action} · {key('keys_add')}: import · {key('keys_close')}: hide"


def startup_failure(code):
    message='Could not load the selected rice.'
    if code is not None: message+=f' The shell launcher exited with code {code}.'
    return message
