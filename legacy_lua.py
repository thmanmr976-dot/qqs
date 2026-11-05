"""Editable Lua themes with one-time migration from older JSON settings."""
import json
import re
import os
import shutil
import subprocess
from pathlib import Path
from PySide6.QtGui import QColor

DEFAULTS=Path(__file__).resolve().parent/'themes'
CONFIG=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'qqs'
LUA_READER=r'''
local safe = {math=math, string=string, table=table, tonumber=tonumber, tostring=tostring,
              pairs=pairs, ipairs=ipairs, type=type, assert=assert}
local chunk, err = loadfile(arg[1], 't', safe)
if not chunk then error(err) end
local result = chunk()
assert(type(result)=='table', 'Theme must return a Lua table')
local function hex(s)
    return (s:gsub('.', function(c) return string.format('%02x', string.byte(c)) end))
end
for key,value in pairs(result) do
    assert(type(key)=='string', 'Theme keys must be strings')
    local kind=type(value)
    assert(kind=='string' or kind=='number' or kind=='boolean', 'Unsupported theme value for '..key)
    print(hex(key)..'\t'..kind..'\t'..hex(tostring(value)))
end
'''

def read_lua(path):
    interpreter=next((shutil.which(name) for name in ('lua','lua5.5','lua5.4','lua5.3','lua5.2') if shutil.which(name)),None)
    if not interpreter: raise ValueError('Lua 5.2 or newer is required. Install Lua using your package manager.')
    try:
        run=subprocess.run([interpreter,'-',str(path)],input=LUA_READER,capture_output=True,text=True,timeout=2)
    except subprocess.TimeoutExpired: raise ValueError(f'{path}: Lua theme exceeded the 2-second time limit.')
    if run.returncode: raise ValueError(f'{path}: {run.stderr.strip()}')
    values={}
    try:
        for line in run.stdout.splitlines():
            key,kind,value=line.split('\t')
            key=bytes.fromhex(key).decode('utf-8');value=bytes.fromhex(value).decode('utf-8')
            if kind=='boolean': value=value=='true'
            elif kind=='number':
                numeric=float(value)
                if not numeric.is_integer(): raise ValueError('Numeric settings must be integers')
                value=int(numeric)
            values[key]=value
    except (ValueError,UnicodeError) as e: raise ValueError(f'{path}: invalid Lua theme output: {e}')
    return values

def write_lua(path,values):
    lines=['-- qqs appearance settings. Edit values and reopen the list to apply.','return {']
    for key,value in values.items():
        encoded=str(value).lower() if isinstance(value,(bool,int)) else json.dumps(value,ensure_ascii=False)
        label=key if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',key) else '['+json.dumps(key)+']'
        lines.append('  '+label+' = '+encoded+',')
    lines.append('}\n');path.write_text('\n'.join(lines),encoding='utf-8')
