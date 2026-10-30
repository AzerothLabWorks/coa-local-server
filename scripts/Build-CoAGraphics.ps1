#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceDirectory,
    [Parameter(Mandatory)][string]$BuildDirectory,
    [string]$PythonExecutable = 'python'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repository = Split-Path -Parent $PSScriptRoot
$Revision = '4e31ddf53a326ba9c0ad03488b4c30f7ce23c969'
$Upstream = 'https://github.com/jealous-sound/coa-vfog.git'
$Patch = Join-Path $Repository 'client-patches\coa-graphics\ripple-state-preservation.patch'

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Plain-Path([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            Require (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) ('Linked path refused: ' + $Path)
        }
        $parent = [IO.Directory]::GetParent($cursor)
        $cursor = if ($parent) { $parent.FullName } else { $null }
    }
    return $full
}
function Run([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Command failed: ' + $Program) }
}

$SourceDirectory = Plain-Path $SourceDirectory
$BuildDirectory = Plain-Path $BuildDirectory
Require (-not (Test-Path -LiteralPath $SourceDirectory) -and -not (Test-Path -LiteralPath $BuildDirectory)) 'Source and build directories must both be new.'
Require ((Test-Path -LiteralPath (Split-Path -Parent $SourceDirectory)) -and (Test-Path -LiteralPath (Split-Path -Parent $BuildDirectory))) 'Create the parent directories first.'
Require ($SourceDirectory -ne $BuildDirectory -and -not $SourceDirectory.StartsWith($BuildDirectory + '\',[StringComparison]::OrdinalIgnoreCase) -and -not $BuildDirectory.StartsWith($SourceDirectory + '\',[StringComparison]::OrdinalIgnoreCase)) 'Use separate source and build directories.'
foreach ($command in @('git','cmake','ctest')) { $null = Get-Command $command -ErrorAction Stop }
$pythonCommand = Get-Command $PythonExecutable -CommandType Application -ErrorAction Stop
$PythonExecutable = $pythonCommand.Source
Run -Program $PythonExecutable -Arguments @('-c','import sys; assert sys.version_info >= (3, 8), "Python 3.8 or newer is required"')
$null = Plain-Path $Patch
$PatchHash = (Get-FileHash -LiteralPath $Patch).Hash.ToLowerInvariant()
Run -Program git -Arguments @('clone','--no-checkout',$Upstream,$SourceDirectory)
Run -Program git -Arguments @('-C',$SourceDirectory,'checkout','--detach',$Revision)
$actual = & git -C $SourceDirectory rev-parse HEAD
Require ($LASTEXITCODE -eq 0 -and $actual.Trim() -ceq $Revision) 'Upstream revision mismatch.'
Run -Program git -Arguments @('-C',$SourceDirectory,'apply','--check',$Patch)
Run -Program git -Arguments @('-C',$SourceDirectory,'apply',$Patch)
$ini = Join-Path $SourceDirectory 'CoAVolFog.ini'
$original = [IO.File]::ReadAllText($ini)
Require (([regex]::Matches($original,'(?m)^FarClipMax=1583\r?$')).Count -eq 1) 'Unexpected view-distance preset.'
[IO.File]::WriteAllText($ini, ($original -replace '(?m)^FarClipMax=1583\r?$', 'FarClipMax=0'), [Text.UTF8Encoding]::new($false))
Run -Program cmake -Arguments @('-S',$SourceDirectory,'-B',$BuildDirectory,'-G','Visual Studio 17 2022','-A','Win32',('-DPython3_EXECUTABLE=' + $PythonExecutable))
Run -Program cmake -Arguments @('--build',$BuildDirectory,'--config','Release')
$testInventory = & ctest --test-dir $BuildDirectory -C Release --show-only=json-v1
Require ($LASTEXITCODE -eq 0) 'CTest inventory failed.'
$testNames = @((($testInventory -join "`n") | ConvertFrom-Json).tests | ForEach-Object { $_.name })
Require ('vfog_harness' -in $testNames -and 'comments' -in $testNames) 'Required graphics tests were not registered.'
Run -Program ctest -Arguments @('--test-dir',$BuildDirectory,'-C','Release','--no-tests=error','--output-on-failure')
$files = [ordered]@{}
foreach ($name in @('version.dll','CoAVolFog.dll','CoAVolFog.ini','fogdata.bin','waterdata.bin')) {
    $path = Join-Path (Join-Path $BuildDirectory 'Release') $name
    $null = Plain-Path $path
    $files[$name] = (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
}
$receipt = [ordered]@{schema=1; upstream=$Upstream; revision=$Revision; patch_sha256=$PatchHash; files=$files; tests=[ordered]@{status='passed'; names=$testNames}; installed=$false; utc=[DateTimeOffset]::UtcNow.ToString('o')}
$receiptPath = Join-Path $BuildDirectory 'coa-graphics-build.json'
Require (-not (Test-Path -LiteralPath $receiptPath)) 'Build receipt already exists.'
[IO.File]::WriteAllText($receiptPath,($receipt | ConvertTo-Json -Depth 6) + "`n",[Text.UTF8Encoding]::new($false))
Write-Output ('Qualified graphics build prepared: ' + $receiptPath)
Write-Output 'No client files were changed. Read docs/client-setup.md before any installation.'
