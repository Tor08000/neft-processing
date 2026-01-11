@echo off
setlocal

set "VERSION=%~1"
if "%VERSION%"=="" (
  echo [release][ERROR] usage: scripts\release\generate_release_notes.cmd vYYYY.MM.PATCH
  exit /b 1
)

set "LAST_TAG="
for /f "delims=" %%i in ('git describe --tags --abbrev^=0 2^>NUL') do set "LAST_TAG=%%i"

set "RANGE=HEAD"
if not "%LAST_TAG%"=="" set "RANGE=%LAST_TAG%..HEAD"

set "OUTPUT=RELEASE_NOTES_%VERSION%.md"

powershell -NoProfile -Command "$version='%VERSION%'; $range='%RANGE%'; $lastTag='%LAST_TAG%'; $output='%OUTPUT%'; $log = git log $range --pretty=format:'%s|%h'; $features=@(); $fixes=@(); $migrations=@(); $breaking=@(); foreach ($line in $log) { if ([string]::IsNullOrWhiteSpace($line)) { continue }; $parts=$line -split '\|',2; $subject=$parts[0]; $hash=$parts[1]; $entry = '- ' + $subject + ' (' + $hash + ')'; if ($subject -match '(?i)^feat') { $features += $entry } elseif ($subject -match '(?i)^fix') { $fixes += $entry } elseif ($subject -match '(?i)migration|migrate|alembic') { $migrations += $entry } elseif ($subject -match '(?i)breaking|!:') { $breaking += $entry } else { $fixes += $entry } }; $content = @(); $content += '# Release ' + $version; $content += ''; if ($lastTag) { $content += 'Since: ' + $lastTag; $content += '' } $content += '## Features'; if ($features.Count -eq 0) { $content += '- (none)' } else { $content += $features }; $content += ''; $content += '## Fixes'; if ($fixes.Count -eq 0) { $content += '- (none)' } else { $content += $fixes }; $content += ''; $content += '## Migrations'; if ($migrations.Count -eq 0) { $content += '- (none)' } else { $content += $migrations }; $content += ''; $content += '## Breaking changes'; if ($breaking.Count -eq 0) { $content += '- (none)' } else { $content += $breaking }; $content += ''; $content | Set-Content -Path $output -Encoding UTF8; Write-Host ('[release] notes generated: ' + $output)" 

exit /b 0
