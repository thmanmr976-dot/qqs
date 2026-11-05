import os
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse, quote

MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 12000

def github_url(url, ref=''):
    p = urlparse(url.strip())
    parts = p.path.strip('/').split('/')
    if p.scheme != 'https' or p.netloc.lower() != 'github.com' or len(parts) != 2:
        raise ValueError('Enter a GitHub repository URL such as https://github.com/owner/repo.')
    owner, repo = parts
    repo = repo.removesuffix('.git')
    if not all(re.fullmatch(r'[\w.-]+', s) and s not in ('.', '..') for s in (owner, repo)):
        raise ValueError('Invalid GitHub repository URL.')
    return f'https://api.github.com/repos/{owner}/{repo}/zipball/' + quote(ref.strip(), safe='')

def download(url, destination):
    request = urllib.request.Request(url, headers={'User-Agent': 'qqs', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=45) as response, open(destination, 'wb') as output:
        total = 0
        while chunk := response.read(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError('Download exceeds the 100 MB limit.')
            output.write(chunk)

def extract_archive(archive, library):
    library = Path(library)
    library.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.import-', dir=library))
    try:
        with zipfile.ZipFile(archive) as z:
            entries = z.infolist()
            if len(entries) > MAX_FILES or sum(i.file_size for i in entries) > MAX_BYTES:
                raise ValueError('Archive exceeds the limit of 100 MB or 12,000 entries.')
            for i in entries:
                target = (staging / i.filename).resolve()
                mode = i.external_attr >> 16
                if not target.is_relative_to(staging.resolve()) or stat.S_ISLNK(mode) or '\\' in i.filename:
                    raise ValueError('Archive contains an unsafe path or a symbolic link.')
                if i.flag_bits & 1:
                    raise ValueError('Encrypted ZIP files are not supported.')
            z.extractall(staging)
        from backends import discover_entries
        for item in entries:
            target=staging/item.filename
            if target.is_file():target.chmod(0o755 if (item.external_attr>>16)&0o111 else 0o644)
        discover_entries(staging)
        name = re.sub(r'[^\w.-]+', '-', Path(archive).stem)[:60] or 'interface'
        dest = library / name
        n = 2
        while dest.exists():
            dest = library / f'{name}-{n}'
            n += 1
        staging.rename(dest)
        return dest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

def save_text(path, text):
    path = Path(path)
    backup = path.with_name(path.name + '.bak')
    shutil.copy2(path, backup)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.save-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
