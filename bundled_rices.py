"""Install the included rice snapshots without copying machine-specific state."""
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from runtime import write_json

BASE = Path(__file__).resolve().parent / 'bundled-rices'


def within(root, relative):
    value = Path(relative)
    target = (root / value).resolve()
    if value.is_absolute() or not target.is_relative_to(root.resolve()):
        raise ValueError('Bundled rice paths must remain inside their folder.')
    return target


def install_bundled(data=None, bundle=BASE):
    bundle = Path(bundle)
    index = bundle / 'index.json'
    if not index.is_file():
        return 0
    if data is None:
        data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'quickshell-studio'
    data = Path(data)
    prefs_path = data / 'preferences.json'
    prefs = json.loads(prefs_path.read_text()) if prefs_path.exists() else {}
    rices = prefs.setdefault('rices', [])
    records = json.loads(index.read_text())['rices']
    added = 0
    for record in records:
        slug = record['id']
        if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', slug):
            raise ValueError('Invalid bundled rice ID.')
        source = within(bundle, record['directory'])
        if not source.is_dir() or not within(source, record['entry']).is_file():
            raise ValueError('Bundled rice entry is missing: ' + slug)
        if any(path.is_symlink() for path in source.rglob('*')):
            raise ValueError('Bundled rice snapshots must not contain symbolic links.')
        existing = next((rice for rice in rices if rice.get('bundle_id') == slug), None)
        if existing:
            continue
        library = data / 'interfaces'
        library.mkdir(parents=True, exist_ok=True)
        destination = library / ('bundled-' + slug)
        # A previous or manually edited copy belongs to the user. Keep it intact.
        suffix = 2
        while destination.exists():
            destination = library / ('bundled-' + slug + '-' + str(suffix))
            suffix += 1
        with tempfile.TemporaryDirectory(prefix='.qqs-bundle-', dir=library) as temporary:
            staged = Path(temporary) / 'snapshot'
            shutil.copytree(source, staged)
            staged.rename(destination)
        rice = {key: record[key] for key in ('name', 'source', 'source_kind', 'launch_options') if key in record}
        rice.update(bundle_id=slug, root=str(destination.resolve()), entry=str(within(destination, record['entry'])))
        rices.append(rice)
        added += 1
    if added:
        write_json(prefs_path, prefs)
    return added


if __name__ == '__main__':
    print(f'Added {install_bundled()} bundled rices. Existing copies and settings were preserved.')
