#!/usr/bin/env python3
"""Build a release only after the source and packaged tests both pass."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent

def test(directory):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=directory, env=env, check=True)

def build(output):
    test(BASE)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.qqs-release-', dir=output.parent) as tmp:
        tmp = Path(tmp)
        archive = tmp/'qqs.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(BASE.rglob('*')):
                relative = p.relative_to(BASE)
                if any(part in ('__pycache__', '.venv', '.git', 'work') for part in relative.parts):
                    continue
                if p.is_file() and p.suffix not in ('.zip', '.pyc'):
                    z.write(p, str(Path('qqs')/relative))
        unpacked = tmp/'unpacked'
        with zipfile.ZipFile(archive) as z:
            z.extractall(unpacked)
        test(unpacked/'qqs')
        shutil.copyfile(archive, output)
    print('Validated source and packaged release: '+str(output))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', default=str(BASE.parent/'qqs.zip'))
    build(parser.parse_args().output)
