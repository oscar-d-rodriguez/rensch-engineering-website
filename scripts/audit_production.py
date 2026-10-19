#!/usr/bin/env python3
"""Compare public production files with main/PR #1 over read-only FTP.
Only changed public files are saved; PHP source is hashed but never saved.
"""
from concurrent.futures import ThreadPoolExecutor
import ftplib
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import ssl
import subprocess
import threading
from prepare_deploy import ASSET_DIRS, ROOT_FILES, select_site_files

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.production-audit'
REFS = os.environ.get('FTP_AUDIT_REFS', 'origin/main').split()
if not REFS or REFS[0] != 'origin/main':
    raise ValueError('The first audit reference must be origin/main')


def connect():
    protocol = os.environ.get('FTP_PROTOCOL', 'ftps')
    if protocol not in {'ftp', 'ftps'}:
        raise ValueError('Audit supports FTP or explicit FTPS only')
    c = ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=45) if protocol == 'ftps' else ftplib.FTP(timeout=45)
    c.connect(os.environ['FTP_SERVER'], int(os.environ.get('FTP_PORT', '21')))
    c.login(os.environ['FTP_USERNAME'], os.environ['FTP_PASSWORD'])
    if protocol == 'ftps':
        c.prot_p()
    c.cwd(os.environ['FTP_SERVER_DIR'])
    return c


def selected(path):
    return bool(select_site_files([path])) or (len(PurePosixPath(path).parts) == 1 and PurePosixPath(path).suffix in {'.html', '.shtml', '.css', '.js'})


def remote_files(c):
    files = []
    def walk(folder):
        for name, facts in c.mlsd(folder or '.'):
            if name in {'.', '..'} or name.startswith('.') or name.endswith('.pages'):
                continue
            if any(v in name for v in ['/', '\\', '\r', '\n']):
                raise ValueError('Unexpected remote filename')
            path = folder + '/' + name if folder else name
            if facts.get('type') == 'dir':
                if folder or name in ASSET_DIRS or name == 'php':
                    walk(path)
            elif facts.get('type') == 'file' and selected(path):
                files.append(path)
    walk('')
    return sorted(files)


def trees():
    result = {}
    for ref in REFS:
        entries = {}
        output = subprocess.check_output(['git', 'ls-tree', '-r', ref], cwd=ROOT, text=True)
        for line in output.splitlines():
            meta, name = line.split('\t', 1)
            if selected(name):
                entries[name] = meta.split()[2]
        result[ref] = entries
    return result


def main():
    refs = trees()
    c = connect()
    try:
        paths = remote_files(c)
    finally:
        c.close()
    OUTPUT.mkdir(exist_ok=True)
    clients = []
    lock = threading.Lock()
    local = threading.local()
    def inspect(path):
        if not hasattr(local, 'ftp'):
            local.ftp = connect()
            with lock:
                clients.append(local.ftp)
        stream = BytesIO()
        local.ftp.retrbinary('RETR ' + path, stream.write)
        data = stream.getvalue()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        matches = {ref: refs[ref].get(path) == blob for ref in REFS}
        saved = False
        if not matches[REFS[0]] and not path.endswith('.php'):
            target = OUTPUT / 'production' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            saved = True
        return {'path': path, 'size': len(data), 'gitBlob': blob, 'sha256': hashlib.sha256(data).hexdigest(), 'matches': matches, 'savedPublicContent': saved}
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(inspect, paths))
    finally:
        for client in clients:
            client.close()
    report = {'method': 'FTP read-only directory listing and RETR; no uploads, renames or deletes',
              'refs': {ref: subprocess.check_output(['git', 'rev-parse', ref], cwd=ROOT, text=True).strip() for ref in REFS},
              'records': records,
              'missingFromProduction': {ref: sorted(set(refs[ref]) - set(paths)) for ref in REFS},
              'differentFromMain': [r['path'] for r in records if not r['matches'][REFS[0]]],
              'excluded': 'Account backup directories, dotfiles, server logs/configuration, desktop metadata, Apple Pages source bundles and CGI hosting files. PHP source content is not saved.'}
    (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2))
    print('Read-only audit complete: ' + str(len(records)) + ' production application files hashed.')
    print('Files different from main: ' + str(len(report['differentFromMain'])))
    print('No uploads, renames or deletes were performed.')


if __name__ == '__main__':
    main()
