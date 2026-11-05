"""Rasi theme syntax for qqs: selectors, variables, imports and typed values."""
import json
import re
from pathlib import Path


def without_comments(source):
    output=[];i=0;quoted=False
    while i<len(source):
        if quoted:
            output.append(source[i])
            if source[i]=='\\' and i+1<len(source):i+=1;output.append(source[i])
            elif source[i]=='"':quoted=False
            i+=1;continue
        if source[i]=='"':quoted=True;output.append(source[i]);i+=1;continue
        if source.startswith('//',i):
            end=source.find('\n',i);i=len(source) if end<0 else end;continue
        if source.startswith('/*',i):
            depth=1;i+=2
            while depth and i<len(source):
                if source.startswith('/*',i):depth+=1;i+=2
                elif source.startswith('*/',i):depth-=1;i+=2
                else:i+=1
            if depth:raise ValueError('Unclosed Rasi comment.')
            output.append(' ');continue
        output.append(source[i]);i+=1
    return ''.join(output)


def outside_parts(text,separator):
    parts=[];start=0;quoted=False;escaped=False;depth=0
    for i,c in enumerate(text):
        if escaped:escaped=False;continue
        if quoted and c=='\\':escaped=True;continue
        if c=='"':quoted=not quoted
        if not quoted:
            if c in '([':depth+=1
            elif c in ')]':depth-=1
            elif c==separator and depth==0:parts.append(text[start:i]);start=i+1
    if quoted or depth:raise ValueError('Unclosed string or expression in Rasi theme.')
    parts.append(text[start:]);return parts


def parse_file(path,search=(),stack=(),dependencies=None):
    path=Path(path).resolve()
    if dependencies is not None:dependencies.add(path)
    if path in stack:raise ValueError('Circular Rasi import: '+str(path))
    if len(stack)>8:raise ValueError('Too many nested Rasi imports.')
    if path.stat().st_size>1024*1024:raise ValueError('Rasi file exceeds 1 MB: '+str(path))
    text=without_comments(path.read_text(encoding='utf-8'));blocks=[]
    while text.strip():
        text=text.lstrip()
        directive=re.match(r'@(import|theme)\s+("(?:\\.|[^"\\])*")\s*;?',text)
        if directive:
            name=json.loads(directive.group(2));candidate=Path(name).expanduser()
            options=[candidate] if candidate.is_absolute() else [base/candidate for base in (path.parent,*search)]
            options += [p.with_suffix('.rasi') for p in options if not p.suffix]
            target=next((p for p in options if p.is_file()),None)
            if target is None:raise ValueError(f'{path}: import not found: {name}')
            
            if directive.group(1)=='theme':blocks=[b for b in blocks if b[0]=='configuration']
            blocks.extend(parse_file(target,search,(*stack,path),dependencies));text=text[directive.end():];continue
        opening=text.find('{')
        if opening<0:raise ValueError(f'{path}: expected a selector followed by {{.')
        selectors=text[:opening].strip();quoted=False;escaped=False;closing=None
        for i in range(opening+1,len(text)):
            c=text[i]
            if escaped:escaped=False;continue
            if quoted and c=='\\':escaped=True;continue
            if c=='"':quoted=not quoted
            if not quoted and c=='{':raise ValueError(f'{path}: nested selector blocks are not supported.')
            if not quoted and c=='}':closing=i;break
        if closing is None:raise ValueError(f'{path}: missing closing }}.')
        values={}
        for item in outside_parts(text[opening+1:closing],';'):
            if not item.strip():continue
            key,sep,value=item.partition(':')
            if not sep or not re.fullmatch(r'[\w-]+',key.strip()) or not value.strip():raise ValueError(f'{path}: invalid property: {item.strip()}')
            values[key.strip()]=value.strip()
        for selector in selectors.split(','):blocks.append((' '.join(selector.strip().lstrip('#').split()),values.copy()))
        text=text[closing+1:]
    return blocks


def value(raw,variables,seen=()):
    raw=re.sub(r'(\d)\s+px\b',r'\1px',raw.strip())
    if raw.startswith('@'):
        key=raw[1:]
        if key in seen:raise ValueError('Circular Rasi variable: '+key)
        if key not in variables:raise ValueError('Unknown Rasi variable: @'+key)
        return value(variables[key],variables,(*seen,key))
    if raw.startswith('"'):return json.loads(raw)
    if raw in ('true','false'):return raw=='true'
    if re.fullmatch(r'-?\d+(?:px)?',raw):return int(raw.removesuffix('px'))
    if re.fullmatch(r'\d+(?:\.\d+)?%',raw):return raw
    if raw.startswith('#'):
        if not re.fullmatch(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})',raw):raise ValueError('Invalid Rasi color: '+raw)
        # Rasi writes alpha last, Qt writes alpha first.
        if len(raw)==5:return '#'+raw[4]*2+raw[1]*2+raw[2]*2+raw[3]*2
        return '#'+raw[7:9]+raw[1:7] if len(raw)==9 else raw
    rgba=re.fullmatch(r'rgba?\(([^)]+)\)',raw)
    if rgba:
        numbers=[float(p.strip()) for p in rgba.group(1).split(',')]
        if len(numbers) not in (3,4):raise ValueError('Invalid rgb/rgba color.')
        rgb=[max(0,min(255,round(c))) for c in numbers[:3]]
        alpha=max(0,min(255,round(numbers[3]*255))) if len(numbers)==4 else 255
        return '#'+''.join(f'{c:02x}' for c in [alpha,*rgb])
    return raw


SELECTORS={
 'window':{'width':'width','height':'height','background-color':'background','background-image':'background_image','border-color':'border_color','border':'border_width','border-radius':'corner_radius','location':'window_position','x-offset':'window_offset_x','y-offset':'window_offset_y'},
 'mainbox':{'padding':'layout_padding','spacing':'layout_spacing','children':'layout_order'},
 'inputbar':{'spacing':'input_spacing','position':'input_position'},
 'entry':{'font':'input_font','text-color':'input_text_color','background-color':'input_background','border':'input_border_width','border-color':'input_border','border-radius':'input_radius','padding':'input_padding','height':'input_height','placeholder':'placeholder','placeholder-color':'placeholder_color'},
 'button':{'font':'button_font','width':'button_width','height':'button_height','border-radius':'button_radius','background-color':'button_color','text-color':'button_text_color','text':'add_text','enabled':'show_add_button'},
 'button hover':{'background-color':'button_hover_color'},
 'listview':{'columns':'list_columns','lines':'list_lines','spacing':'list_spacing','scrollbar':'show_scrollbar','cycle':'navigation_wrap'},
 'element':{'height':'row_height','border':'row_border_width','border-color':'row_border','border-radius':'row_radius','padding':'row_padding','background-color':'row_background','text-color':'row_text_color','font':'row_font'},
 'element-text':{'text-color':'row_text_color','font':'row_font'},
 'element-icon':{'size':'icon_size'},
 'element selected':{'background-color':'row_selected','text-color':'row_selected_text_color','border-color':'row_selected_border','border':'row_selected_border_width'},
 'element alternate':{'background-color':'row_alternate'},
 'element hover':{'background-color':'row_hover'},
 'title':{'text':'title_text','enabled':'show_title','font':'title_font','text-color':'title_color'},
 'footer':{'text':'footer_text','enabled':'show_footer','font':'footer_font','text-color':'footer_color'},
 'message':{'text':'message','font':'font','text-color':'text_color'},
 'progressbar':{'background-color':'bar_color','border-color':'bar_border_color','border':'bar_border_width','border-radius':'bar_radius','segments':'segments','width':'segment_width','height':'segment_height','spacing':'segment_gap'},
}
FONT_KEYS={'font':'font_size','input_font':'input_font_size','row_font':'row_font_size','button_font':'button_font_size','title_font':'title_font_size','footer_font':'footer_font_size'}

def read_theme(path,defaults,search=(),loading=False,dependencies=None):
    blocks=parse_file(path,search,dependencies=dependencies);variables={};result={}
    for selector,properties in blocks:
        if selector=='*':variables.update(properties)
    for selector,properties in blocks:
        selector=selector.replace('selected.normal','selected').replace('normal.normal','normal')
        if selector=='element normal':selector='element'
        if selector=='configuration':
            aliases={'kb-accept-entry':'keys_accept','kb-row-down':'keys_next','kb-row-up':'keys_previous','kb-cancel':'keys_close','matching':'search_mode','case-sensitive':'search_case_sensitive'}
            mapping={key:aliases.get(key,key.replace('-','_')) for key in properties}
        elif selector=='*':
            aliases={'background-color':'background','text-color':'text_color'}
            mapping={key:aliases.get(key,key.replace('-','_')) for key in properties if aliases.get(key,key.replace('-','_')) in defaults}
        elif selector in SELECTORS:mapping=SELECTORS[selector]
        else:raise ValueError('Unsupported qqs Rasi selector: '+selector)
        for prop,raw in properties.items():
            if selector=='*' and prop not in mapping:continue
            if prop not in mapping:raise ValueError(f'Unsupported property {prop} in {selector}.')
            key=mapping[prop]
            if loading and selector=='footer':key={'footer_text':'footer','footer_color':'text_color','footer_font':'footer_font'}.get(key,key)
            if loading and selector=='window':key={'background':'background'}.get(key,key)
            if key not in defaults:raise ValueError(f'{key} is not available in this theme.')
            if raw=='inherit':continue
            v=value(raw,variables)
            if key=='background_image' and isinstance(v,str) and v.startswith('url(') and v.endswith(')'):v=json.loads(v[4:-1].strip())
            if key=='search_mode' and v=='normal':v='substring'
            if key=='layout_order' and isinstance(v,str) and v.startswith('['):
                names=[name.strip().strip('\"') for name in v.strip('[]').split(',')]
                names=[{'inputbar':'input','listview':'list'}.get(name,name) for name in names]
                result['show_title']='title' in names;result['show_footer']='footer' in names
                v=','.join(names+[name for name in ('title','input','list','footer') if name not in names])
            if key in FONT_KEYS and isinstance(v,str):
                match=re.fullmatch(r'(.+?)\s+(\d+)',v)
                if match:
                    result[FONT_KEYS[key]]=int(match.group(2));v=match.group(1)
            result[key]=v
    return result


def serialize(values):
    lines=['/* qqs Rasi settings. Reopen the launcher or reload to apply. */','configuration {']
    for key,v in values.items():
        encoded=str(v).lower() if isinstance(v,(bool,int)) else json.dumps(v,ensure_ascii=False)
        lines.append('    '+key.replace('_','-')+': '+encoded+';')
    return '\n'.join([*lines,'}',''])
