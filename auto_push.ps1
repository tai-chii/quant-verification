Set-Location "$env:USERPROFILE\verification-lab"
git fetch origin main *> $null
git pull --rebase origin main *> $null
git add -A
$changes = git status --porcelain
if ($changes) {
    git commit -m "auto: $(Get-Date -Format 'yyyy-MM-dd HH:mm')" *> $null
    git push origin main *> $null
}
