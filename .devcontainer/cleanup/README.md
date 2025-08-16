Docker resource cleanup utilities

This folder contains scripts to safely remove Docker containers, images, volumes, and build cache that have not been used in the past N days.

Files
- docker-prune-old.sh  : Bash script (Linux/macOS) — removes containers/images/volumes older than $DAYS (default 30)
- docker-prune-old.ps1 : PowerShell script (Windows) — same functionality

Usage
- Dry-run (Bash):
  DAYS=30 DRY=true bash docker-prune-old.sh
- Actual run (Bash):
  DAYS=30 bash docker-prune-old.sh

- Dry-run (PowerShell):
  .\docker-prune-old.ps1 -Days 30 -DryRun
- Actual run (PowerShell):
  .\docker-prune-old.ps1 -Days 30

Automation
- Linux: create a systemd timer unit that runs the Bash script monthly/daily. Example (place under /etc/systemd/system):
  - docker-prune-old.service
  - docker-prune-old.timer

- Windows: schedule `docker-prune-old.ps1` with Task Scheduler weekly/monthly.

Safety notes
- Scripts attempt to only remove resources older than the specified threshold and not referenced by containers.
- Always run with DRY=true / -DryRun first to verify the list before deleting.

If you want, I can also: 
- Add systemd unit files templates and a `make docker-clean-scheduler` helper to install them (requires root).
- Add GitHub Actions workflow to run the cleanup on a self-hosted runner (if desired).
