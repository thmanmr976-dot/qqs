"""Rasi themes, validation and one-time migration from previous Lua/JSON files."""
import json
import os
import re
import shutil
from pathlib import Path
from PySide6.QtGui import QColor,QKeySequence
from theme_defaults import MENU,LOADING
from rasi import read_theme,serialize

DEFAULTS=Path(__file__).resolve().parent/'themes'
CONFIG=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'qqs'
THEME_FILES={}
ENUMS={'window_position':{'center','north','south','east','west','northeast','northwest','southeast','southwest'},'input_position':{'top','bottom'},'search_mode':{'substring','prefix','fuzzy','disabled'},'list_sort':{'import','name','recent'},'row_alignment':{'left','center','right'},'bar_style':{'segments','line'},'message_alignment':{'left','center','right'}}

def active_format():
    marker=CONFIG/'theme-format'
    if marker.exists():
        selected=marker.read_text(encoding='utf-8').strip()
        if selected not in ('lua','rasi'): raise ValueError('theme-format must contain lua or rasi.')
        return selected
    if (CONFIG/'menu.rasi').exists(): return 'rasi'
    return 'lua'


def theme_path(name):
    return CONFIG/(name+'.'+active_format())


def read_values(path,name,dependencies):
    defaults=MENU if name=='menu' else LOADING
    if path.suffix=='.lua':
        from legacy_lua import read_lua
        values=read_lua(path);dependencies.add(path.resolve())
        preset=values.pop('preset',None)
        if preset:
            if name!='menu' or preset not in ('qqs-original','qqs-dark','qqs-grid','qqs-minimal','qqs-liquid-glass'):
                raise ValueError('Unsupported Lua preset: '+str(preset))
            values={**read_theme(DEFAULTS/'presets'/(preset+'.rasi'),defaults,(CONFIG,DEFAULTS/'presets'),dependencies=dependencies),**values}
        unknown=set(values)-set(defaults)
        if unknown: raise ValueError('Unknown Lua theme settings: '+', '.join(sorted(unknown)))
        return values
    return read_theme(path,defaults,(CONFIG,DEFAULTS/'presets'),loading=name=='loading',dependencies=dependencies)


def load_theme(name):
    CONFIG.mkdir(parents=True,exist_ok=True)
    defaults=dict(MENU if name=='menu' else LOADING)
    path=theme_path(name)
    if not path.exists():
        legacy=CONFIG/(name+'.json')
        if legacy.exists():
            values=json.loads(legacy.read_text())
            if not isinstance(values,dict): raise ValueError('Legacy theme must be an object.')
            if name=='menu':
                for key in ('width','height','font_size','row_height','corner_radius','row_radius'):
                    if key in values:values[key]=min(values[key],defaults[key])
            write_theme(path,{key:v for key,v in values.items() if key in defaults})
            backup=legacy.with_suffix('.json.bak')
            if not backup.exists():legacy.rename(backup)
        else:write_theme(path,defaults)
    dependencies=set();values=read_values(path,name,dependencies)
    result=validate_theme(values,defaults,path,name)
    THEME_FILES[name]=dependencies
    return result


def write_theme(path,values):
    if path.suffix=='.lua':
        from legacy_lua import write_lua
        write_lua(path,values)
    else:path.write_text(serialize(values),encoding='utf-8')


def set_format(selected):
    if selected not in ('lua','rasi'):raise ValueError('Unknown theme format.')
    if selected==active_format():return
    values={name:load_theme(name) for name in ('menu','loading')}
    for name,theme in values.items():
        destination=CONFIG/(name+'.'+selected)
        if destination.exists():shutil.copy2(destination,destination.with_suffix(destination.suffix+'.bak'))
        write_theme(destination,theme)
    marker=CONFIG/'theme-format';temp=marker.with_suffix('.tmp');temp.write_text(selected+'\n');temp.replace(marker)


def validate_theme(values,defaults,path,name):
    for key,default in defaults.items():
        v=values.get(key,default)
        if isinstance(default,bool):
            if not isinstance(v,bool):raise ValueError(f'{path}: {key} must be true or false.')
        elif isinstance(default,int):
            if key.endswith('padding') and isinstance(v,str) and re.fullmatch(r'\d+(?:px)?(?:\s+\d+(?:px)?){0,3}',v):pass
            elif key in ('width','height') and isinstance(v,str) and v.endswith('%'):
                if not 1<=float(v[:-1])<=100:raise ValueError('Window size percentage must be 1% to 100%.')
            elif type(v) is not int or not (-8192 if key in ('window_offset_x','window_offset_y') else 0)<=v<=60000:
                raise ValueError(f'{path}: invalid numeric value for {key}.')
        elif not isinstance(v,str):raise ValueError(f'{path}: {key} must be text.')
        if key in ('background_opacity','background_image_opacity','glass_strength') and not 0<=v<=100:raise ValueError(f'{key} must be 0 to 100.')
        if key=='list_columns' and not 1<=v<=12:raise ValueError('list-columns must be 1 to 12.')
        if key in ENUMS and v not in ENUMS[key]:raise ValueError(f'{path}: {key} must be one of '+', '.join(sorted(ENUMS[key])))
        if v and (key.endswith('_color') or key.endswith('_background') or key in ('background','row_hover','row_selected','row_alternate','input_border','row_border','row_selected_border')) and not QColor(v).isValid():
            raise ValueError(f'{path}: invalid color for {key}.')
        defaults[key]=v
    if name=='loading' and defaults['startup_timeout_ms']<=defaults['minimum_display_ms']:
        raise ValueError('startup-timeout-ms must be greater than minimum-display-ms.')
    if name=='menu':
        fields=[field.strip() for field in defaults['search_fields'].split(',')]
        if not fields or any(field not in ('name','source','path') for field in fields):
            raise ValueError('search-fields must contain name, source or path.')
        order=[p.strip() for p in defaults['layout_order'].split(',')]
        if len(order)!=4 or set(order)!={'title','input','list','footer'}:raise ValueError('layout-order must contain title,input,list,footer exactly once.')
        for key in ('keys_accept','keys_next','keys_previous','keys_close','keys_context','keys_add','keys_reload'):
            if not defaults[key].strip():raise ValueError(f'{key} cannot be empty.')
            for sequence in re.split(r'[;,]',defaults[key]):
                if sequence.strip() and not QKeySequence(sequence.strip().replace('Control+','Ctrl+')).toString():
                    raise ValueError(f'{key}: invalid shortcut {sequence.strip()}')
    return defaults
