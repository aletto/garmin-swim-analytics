# Privacy and first publication

Private storage defaults to `~/.local/share/swim-analytics`. Set `SWIM_ANALYTICS_HOME` or pass `--data-dir` before the subcommand to use another private directory. The archive requires owner-only directory permissions. Keep raw exports, account archives, token stores, local configuration, normalized datasets and reports outside the checkout. The Garmin key may be kept in the ignored local `.env` with owner-only permissions. Keep the key out of issues, logs and shell history. Use a separate archive per Garmin account.

Git exclusions cover common data formats, archives, credentials and local artifact directories. Use synthetic fixtures generated from scratch. An anonymized real FIT may still contain timestamps, identifiers and health data. Logs and screenshots should also come from synthetic sessions. The CLI's normal output includes only message counts and import status. Review any provider logs independently.

## Before the first commit and push

1. Review the MIT license and copyright attribution.
2. Review `git diff --cached --name-only` and the staged content locally after staging explicit project files. Run `python scripts/check_public_files.py` against the index. This check detects ignored paths that were force-added. It cannot identify personal information saved in a permitted file.
3. With Gitleaks installed, scan the index with `gitleaks git --staged --redact` and review prior history with `gitleaks git --redact` if history exists. The GitHub workflow provides a second check once enabled.
4. Obtain separate explicit approval to create or push the GitHub repository.
