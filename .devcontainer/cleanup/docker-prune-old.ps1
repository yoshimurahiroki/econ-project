# PowerShell script to remove docker resources not used in the last N days
param(
  [int]$Days = 30,
  [switch]$DryRun
)

Write-Host "Docker prune older than $Days days (DryRun=$DryRun)"

# Helper
function Run-If($cmd) {
  if ($DryRun) { Write-Host "DRY: $cmd" } else { iex $cmd }
}

# Containers
$cutoff = (Get-Date).ToUniversalTime().AddDays(-$Days)
$oldContainers = docker ps -a --format "{{.ID}} {{.CreatedAt}}" | ForEach-Object {
  $parts = $_ -split ' ', 2
  $id = $parts[0]
  $created = [datetime]::Parse($parts[1])
  if ($created -lt $cutoff) { $id }
}
if ($oldContainers) { Write-Host "Removing containers:"; $oldContainers; Run-If "docker rm $($oldContainers -join ' ')" }

# Images not referenced by containers
$images = docker images --format "{{.ID}} {{.CreatedAt}}" | ForEach-Object {
  $parts = $_ -split ' ', 2
  $id = $parts[0]
  $created = [datetime]::Parse($parts[1])
  $inUse = (docker ps -a --filter "ancestor=$id" --format '{{.ID}}' | Measure-Object).Count
  if ($created -lt $cutoff -and $inUse -eq 0) { $id }
}
if ($images) { Write-Host "Removing images:"; $images; Run-If "docker rmi $($images -join ' ')" }

# Volumes
$volumes = docker volume ls -q | ForEach-Object {
  $v = $_
  $meta = docker volume inspect $v | ConvertFrom-Json
  $created = [datetime]::Parse($meta[0].CreatedAt)
  if ($created -lt $cutoff) {
    $inUse = (docker ps -a --filter volume=$v --format '{{.ID}}' | Measure-Object).Count
    if ($inUse -eq 0) { $v }
  }
}
if ($volumes) { Write-Host "Removing volumes:"; $volumes; Run-If "docker volume rm $($volumes -join ' ')" }

# Prune builder cache
Run-If "docker builder prune -af"
# Prune dangling
Run-If "docker system prune -af --volumes"

Write-Host "Done"
