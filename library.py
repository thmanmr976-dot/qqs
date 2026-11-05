"""Resolve local shell entry points, ZIP archives and GitHub repositories."""
from pathlib import Path
from urllib.parse import urlparse, unquote
from core import github_url
from backends import discover_entries,backend_for

def resolve_source(text):
    text=text.strip()
    if text.startswith('https://') or text.startswith('http://'):
        p=urlparse(text); parts=p.path.strip('/').split('/')
        ref=''
        if len(parts)>=4 and parts[2]=='tree':
            ref=unquote('/'.join(parts[3:])); parts=parts[:2]
        url=f'{p.scheme}://{p.netloc}/'+ '/'.join(parts)
        return 'github',github_url(url,ref),parts[1].removesuffix('.git')
    if text.startswith('file://'): text=unquote(urlparse(text).path)
    path=Path(text).expanduser().resolve()
    if not path.exists(): raise ValueError('Local path does not exist: '+str(path))
    if path.is_file() and path.suffix.lower()=='.zip': return 'zip',str(path),path.stem
    if path.is_file():backend_for(path)
    return 'local',str(path),path.stem if path.is_file() else path.name

def entry_files(path):
    return discover_entries(path)


def source_metadata(text):
    kind, location, _ = resolve_source(text)
    if kind == 'github':
        parsed = urlparse(text.strip())
        source = f'https://github.com{parsed.path.rstrip("/")}'
        return {'source_kind':kind, 'source':source}
    return {'source_kind':kind, 'source':location}


def infer_legacy_source(rice):
    """Recover a repository URL only when its name matches the extracted folder."""
    if rice.get('source'): return rice
    import re
    entry = Path(rice['entry'])
    root = Path(rice.get('root',str(entry.parent)))
    folders = [entry.parent, root]
    if root.is_dir(): folders.extend(p for p in root.iterdir() if p.is_dir())
    for folder in folders:
        readme = folder/'README.md'
        if not readme.is_file() or readme.stat().st_size > 500000: continue
        text = readme.read_text(encoding='utf-8',errors='replace')
        for owner,repo in re.findall(r'https://github\.com/([\w.-]+)/([\w.-]+)',text):
            repo=repo.removesuffix('.git')
            prefix=owner+'-'+repo
            if folder.name.lower().startswith(prefix.lower()) and re.fullmatch(r'-?[0-9a-f]{6,40}',folder.name[len(prefix):],re.I):
                return {**rice,'source_kind':'github','source':f'https://github.com/{owner}/{repo}'}
    return rice


def rice_folder(rice):
    root=Path(rice.get('root',str(Path(rice['entry']).parent)))
    return root.parent if root.is_file() else root
