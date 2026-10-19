# Automatic production deployment

A push to `main` (including a merged pull request) validates the repository and syncs the public website payload to the existing hosting account. Pull requests only run validation; they do not receive FTP credentials or deploy. This workflow does not merge any pull request.

## One-time hosting setup — required before merging

1. Confirm the hosting provider, FTP/FTPS hostname, port and exact live website directory. The path is relative to the FTP account's login root; `/public_html/` is only an example, not a configured default. SFTP/SSH needs a different deployment implementation.
2. Back up the current live site using the hosting control panel. Review that this repository matches production: the first deployment syncs the full allowed site payload, not just the navigation diff.
3. In repository **Settings → Secrets and variables → Actions**, add these secrets (or create environment secrets in the `production` environment):

   | Secret | Value |
   |---|---|
   | `FTP_SERVER` | FTP hostname only, without an ftp:// prefix |
   | `FTP_USERNAME` | Hosting FTP account username |
   | `FTP_PASSWORD` | FTP account password; enter it in GitHub, not chat or source files |
   | `FTP_SERVER_DIR` | Confirmed production directory, ending with `/` |

4. Set repository variables `FTP_PROTOCOL` and `FTP_PORT` if needed. Defaults are explicit `ftps` and port `21`. Supported protocols: `ftps`, `ftps-legacy`, `ftp`. Certificate validation is strict. Use the protocol supported by the host; an FTP account's settings do not imply SFTP support.
5. Once the workflow is on `main`, open **Actions → Validate and deploy production → Run workflow** with **dry_run enabled** and inspect the proposed sync. Then run it with dry_run disabled for the first real sync and verify the live site. The merge that first introduces the workflow itself triggers a real deployment if valid secrets are already configured; if configuration is missing, it stops before connecting. For a preview before that first merge, configure a temporary test copy/hosting directory and its credentials deliberately; the production job does not run from feature branches.

## What is uploaded

`scripts/prepare_deploy.py` copies only tracked public site files into `.deploy/`: the eight HTML/error pages, layout stylesheet, public asset directories, project/career/service documents and `php/contact-form.php`.

The payload excludes `.git`, `.github`, scripts, tests, docs, secrets/dotfiles, account backup directories, FTP quota files, server logs, PHP server configuration, desktop metadata and Apple Pages source bundles. `.deploy/` is ignored by Git.

The sync action is pinned to a commit. `dangerous-clean-slate` is false: unrelated server files are not wiped. The state file `.rensch-website-deploy-state.json` tracks managed files; a file removed from a later managed payload can be deleted on the server. Keep this state file intact. A first sync can overwrite matching production files, so a hosting backup is required operational preparation.

## Release and rollback

Review and merge a completed component/page PR into `main`; confirm the deploy job succeeds, then check the live site. Production deployments are serialized and running transfers are not cancelled by newer merges. FTP sync is not an atomic release: visitors may briefly see a mix of files during transfer, and a failed sync may leave a partial update.

Rollback: revert the merged code change through GitHub and merge the revert into `main`; this triggers a new sync. Restore the hosting backup if the site needs immediate recovery or server-managed files were affected. Reverting the workflow's own introduction would also remove automatic deployment, so restore that deployment manually or keep the workflow while reverting site code.

No production upload has been tested until credentials and the correct target folder are configured. The workflow does not create backups, set up hosting, or send a notification outside GitHub's normal Actions UI.

## Read-only connection checks and production reconciliation

The hosting connection was verified using the provider's confirmed Cyberduck settings: FTP on port 21, and `/` relative to this FTP account. Repository variables explicitly select FTP; the workflow defaults to FTPS when not configured. Plain FTP is unencrypted. Secrets remain in GitHub.

`FTP_PREFLIGHT_ENABLED=true` enables the read-only connection job for pull requests from this repository (not forks). `FTP_PRODUCTION_AUDIT=true` additionally lists and hashes public application files over FTP and saves comparison evidence as a seven-day artifact. It never uploads, renames or deletes server files. PHP source is hashed but never included in the artifact. The audit compares against `origin/main` by default; an optional space-separated `FTP_AUDIT_REFS` variable can include other fetched branch references, with `origin/main` first. Disable the full audit flag after reconciliation to avoid repeating a full download on routine PR updates.

PR #1 reconciles the already-deployed employee-photo changes plus the additional founder-photo markup and updated `tim.jpg`. Its merged application baseline was verified against 277 production file hashes. The navigation/deployment PR incorporates that baseline, so it preserves the live team content. Hosting configuration, logs, account backups and source-document metadata are deliberately outside the application baseline.
