#!/usr/bin/env bash
# Remove only the service. Keep the repository, configuration and all app data.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]] || ! command -v systemctl >/dev/null; then
  echo "error: this uninstaller requires Linux with systemd" >&2
  exit 1
fi

if [[ -f /etc/systemd/system/pjtracker.service ]]; then
  sudo systemctl disable --now pjtracker.service
  sudo rm -f /etc/systemd/system/pjtracker.service
  sudo systemctl daemon-reload
fi
echo "PJTracker service removed. App files, data and /etc/pjtracker.env are preserved."
