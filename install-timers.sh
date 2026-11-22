#!/bin/bash
# Installs: a health check every minute, a daily backup, and a size limit for system logs. Run once:  sudo bash deploy/install-timers.sh
set -e
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
OWNER="${SUDO_USER:-$USER}"
chmod +x "$PROJECT"/deploy/*.sh
mk() {   # mk <name> <description> <command> <timer line> <user>
  cat > "/etc/systemd/system/$1.service" << UNIT
[Unit]
Description=$2
[Service]
Type=oneshot
User=$5
ExecStart=$3
UNIT
  cat > "/etc/systemd/system/$1.timer" << UNIT
[Unit]
Description=$2
[Timer]
$4
Persistent=true
[Install]
WantedBy=timers.target
UNIT
}
mk tinychat-health "Tiny Chat health check" "$PROJECT/deploy/healthcheck.sh" "OnBootSec=2min
OnUnitActiveSec=1min" root
mk tinychat-backup "Tiny Chat backup" "$PROJECT/deploy/backup.sh" "OnCalendar=daily" "$OWNER"
sed -i "s#^ExecStart=.*backup.sh#&#" /etc/systemd/system/tinychat-backup.service
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\n' > /etc/systemd/journald.conf.d/tinychat.conf
systemctl daemon-reload
systemctl restart systemd-journald
systemctl enable --now tinychat-health.timer tinychat-backup.timer
echo "Installed. Check with: systemctl list-timers | grep tinychat"
