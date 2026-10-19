#!/usr/bin/env python3
"""Read-only FTP/FTPS login and website-directory check; never uploads or deletes."""
import ftplib
import os
from pathlib import PurePosixPath
import ssl

PAGES = {'index.html', 'about.html', 'services.html', 'projects.html', 'careers.html', 'contact.html'}


def main():
    names = ['FTP_SERVER', 'FTP_USERNAME', 'FTP_PASSWORD', 'FTP_SERVER_DIR']
    if any(not os.environ.get(name) for name in names):
        raise SystemExit('FTP check: required GitHub secrets are missing.')
    protocol = os.environ.get('FTP_PROTOCOL', 'ftps')
    if protocol not in {'ftp', 'ftps'}:
        raise SystemExit('This preflight supports FTP and explicit FTPS only.')
    client = (ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=30)
              if protocol == 'ftps' else ftplib.FTP(timeout=30))
    stage = 'connecting'
    try:
        client.connect(os.environ['FTP_SERVER'], int(os.environ.get('FTP_PORT', '21')))
        if protocol == 'ftps':
            stage = 'validating TLS certificate'
            client.auth()
        stage = 'logging in'
        client.login(os.environ['FTP_USERNAME'], os.environ['FTP_PASSWORD'])
        if protocol == 'ftps':
            client.prot_p()
            print('Encrypted FTPS login succeeded.')
        else:
            print('FTP login succeeded on the confirmed plain-FTP connection; traffic is not encrypted.')
        stage = 'checking production folder'
        try:
            client.cwd(os.environ['FTP_SERVER_DIR'])
        except ftplib.error_perm:
            # Remain at the login root. Report only expected public-site matches,
            # never names of private files or other accounts.
            stage = 'checking account login root'
            entries = {PurePosixPath(name.rstrip('/')).name for name in client.nlst()}
            print('Configured production folder is not accessible from this FTP account.')
            print('Expected website pages found at the account login root: ' + str(len(PAGES & entries)) + '/6.')
            print('A public_html directory is visible at the account login root: ' + str('public_html' in entries) + '.')
            raise SystemExit('Confirm the FTP account directory in cPanel; no files were changed.')
        stage = 'listing production folder'
        entries = {PurePosixPath(name.rstrip('/')).name for name in client.nlst()}
        print('Configured production directory is accessible.')
        print('Expected website pages found: ' + str(len(PAGES & entries)) + '/6.')
        if not PAGES.issubset(entries):
            raise SystemExit('The directory does not contain all six expected pages. Confirm the target before deployment.')
        print('Read-only preflight passed. No upload, rename or delete commands were sent.')
    except ssl.SSLCertVerificationError:
        raise SystemExit('FTPS certificate verification failed before login. Confirm the certificate-valid FTP hostname with the host; strict TLS remains enabled.')
    except (ftplib.Error, OSError, ValueError) as error:
        code = str(error)[:3] if str(error)[:3].isdigit() else 'unavailable'
        raise SystemExit('FTP preflight failed while ' + stage + ' (' + type(error).__name__ + ', response code ' + code + '). No upload, rename or delete commands were sent.')
    finally:
        client.close()


if __name__ == '__main__':
    main()
