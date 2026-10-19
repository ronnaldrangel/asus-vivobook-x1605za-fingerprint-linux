#!/usr/bin/env bash
set -Eeuo pipefail

PAM_FILE="/etc/pam.d/common-auth"
BACKUP="$PAM_FILE.elan3212.bak"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo: sudo $0" >&2
  exit 1
fi

if [[ ! -f "$PAM_FILE" ]]; then
  echo "Not found: $PAM_FILE" >&2
  exit 1
fi

if [[ ! -f "$BACKUP" ]]; then
  cp -a "$PAM_FILE" "$BACKUP"
  echo "Backup: $BACKUP"
fi

sed -i 's/pam_fprintd\.so max-tries=1/pam_fprintd.so max-tries=3/' "$PAM_FILE"

if ! grep -q 'pam_fprintd\.so max-tries=3' "$PAM_FILE"; then
  echo "Could not update pam_fprintd max-tries; inspect $PAM_FILE" >&2
  exit 1
fi

grep pam_fprintd "$PAM_FILE"
echo "PAM now allows up to 3 fingerprint attempts. Password fallback remains."
