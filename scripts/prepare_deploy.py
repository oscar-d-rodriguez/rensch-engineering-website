#!/usr/bin/env python3
"""Prepare only tracked public website files for FTP deployment."""
from pathlib import Path, PurePosixPath
import shutil
import subprocess

ROOT_FILES = {'index.html', 'about.html', 'services.html', 'projects.html',
              'careers.html', 'contact.html', 'home.html', '404.shtml', 'layout-styles.css'}
ASSET_DIRS = {'css', 'js', 'images', 'fonts', 'revolution', 'projects', 'services', 'careers'}


def select_site_files(paths):
    selected = []
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid tracked path')
        if any(part.startswith('.') or part.endswith('.pages') for part in path.parts):
            continue
        if path.name.lower() in {'thumbs.db', 'desktop.ini', 'error_log', 'php.ini'}:
            continue
        if name in ROOT_FILES or name == 'php/contact-form.php' or (
                len(path.parts) > 1 and path.parts[0] in ASSET_DIRS):
            selected.append(name)
    # Deterministic payload, with asset copies prepared before the root pages.
    return sorted(selected, key=lambda name: (name in ROOT_FILES, name))


def prepare(root):
    root = Path(root).resolve()
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    files = select_site_files(filter(None, paths))
    if not ROOT_FILES.issubset(files):
        raise ValueError('Missing required website pages/assets')
    # Validate everything before replacing the local staging directory.
    for name in files:
        source = root / name
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
            raise ValueError('Deployment inputs must be regular repository files')
    output = root / '.deploy'
    if output.is_symlink():
        raise ValueError('The local deployment directory cannot be a symlink')
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    for name in files:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    print(f'Prepared {len(files)} public site files in .deploy/')
    return files


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1])
