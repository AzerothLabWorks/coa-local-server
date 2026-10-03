[CmdletBinding(DefaultParameterSetName = 'Prepare')]
param(
    [Parameter(ParameterSetName = 'Prepare')][switch]$Prepare,
    [Parameter(Mandatory, ParameterSetName = 'Install')][switch]$Install,
    [Parameter(Mandatory)][string]$ArtifactDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = 'C:\Users\User\OneDrive\Documents\Wow Modules\coa-local-server'
$QaRoot = 'C:\Users\User\OneDrive\Documents\Wow Modules\qa-client-patch-work\coa-range-20261003'
$StagingRoot = 'C:\Games\Ascension-WOW-Staging'
$LiveRoot = 'C:\Games\Ascension-WOW'
$Tool = 'C:\Users\User\OneDrive\Documents\Wow Modules\qa-client-patch-work\tools\mpqcli.exe'
$BaseHash = '3973dcd6f1b38877bd7c372730b4fc2998e226f41dd6818856038539cd31bfde'
$LiveHash = '00734080f0755da35d70e1ea78131d8bf448b5e8dd49fd0d990b02996e4ffb37'
$ToolHash = '5dc56b130432098d18e911fdf4b3464adf850432b7fbb35003a2feff7c30a79f'
$BaseMemberHash = 'f57253d9f771a8bb24a8707147fc450fbae1a3846d1d6463ff3c9c6cee00002e'
$Member = 'Interface\LibraryXML\LibRangeCheck-2.0\LibRangeCheck-2.0.lua'
$PrototypeName = 'Interface\AddOns\WeakAuras\Prototypes.lua'
$HelperName = 'Interface\AddOns\COAWeakAurasRange'
$StagingArchive = Join-Path $StagingRoot 'Data\patch-B.MPQ'
$LiveArchive = Join-Path $LiveRoot 'Data\patch-B.MPQ'
$Prototype = Join-Path $StagingRoot $PrototypeName
$Helper = Join-Path $StagingRoot $HelperName
$LibraryInput = Join-Path $RepoRoot 'client-patches\coa-range\LibRangeCheck-2.0.lua'
$PatchInput = Join-Path $RepoRoot 'client-patches\coa-range\WeakAuras-GetRange.patch'
$Utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$Allocated = $false
$InstallAttempted = $false
$Phase = 'preflight'

function Require([bool]$Condition, [string]$Reason) {
    if (-not $Condition) { throw $Reason }
}

function File-Hash([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Require-NoLinks([string]$Path, [bool]$PlainClient = $false) {
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            Require (-not $item.LinkType -and -not $item.Target) 'A protected path contains a link or junction.'
            if ($PlainClient) {
                Require (-not ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) 'A client path contains a reparse point.'
            }
        }
        $parent = [System.IO.Directory]::GetParent($cursor)
        $cursor = if ($parent) { $parent.FullName } else { $null }
    }
}

function Require-ArtifactPath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    Require (($full -ceq $ArtifactDirectory) -or $full.StartsWith($ArtifactDirectory + '\', [System.StringComparison]::Ordinal)) 'Work escaped the fixed artifact directory.'
    Require-NoLinks $full
}

function New-PrivateDirectory([string]$Path) {
    Require-NoLinks $Path
    Require (-not (Test-Path -LiteralPath $Path)) 'Existing work evidence must not be overwritten.'
    $null = New-Item -ItemType Directory -Path $Path
    $acl = Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @([System.Security.Principal.WindowsIdentity]::GetCurrent().User, [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
        $acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Write-NewReport([string]$Name, $Value) {
    $path = Join-Path $ArtifactDirectory $Name
    Require-ArtifactPath $path
    Require (-not (Test-Path -LiteralPath $path)) 'Existing evidence must not be overwritten.'
    [System.IO.File]::WriteAllText($path, ($Value | ConvertTo-Json -Depth 12) + "`n", $Utf8)
}

function Require-GameClosed {
    $running = @(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -in @('Ascension', 'Wow', 'Wow-64', 'MMgr64') })
    Require ($running.Count -eq 0) 'Exit every game client and memory-manager process before installation.'
}

function Invoke-Mpq([string[]]$Arguments) {
    Require ((File-Hash $Tool) -eq $ToolHash) 'The reviewed MPQ tool changed.'
    $output = @(& $Tool @Arguments 2>&1)
    Require ($LASTEXITCODE -eq 0) ('MPQ operation failed: ' + $Arguments[0])
    return @($output | ForEach-Object { $_.ToString() })
}

function Archive-Names([string]$Archive) {
    $names = @(Invoke-Mpq -Arguments @('list', '--all', $Archive) | Where-Object { $_ -ne '' })
    Require ($names.Count -eq 1406) 'The archive must retain exactly 1406 named members.'
    $exact = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $folded = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $names) {
        Require ($exact.Add($name) -and $folded.Add($name)) 'Archive member names collide.'
        Require (-not [System.IO.Path]::IsPathRooted($name) -and $name -notmatch '(^|[\\/])\.\.([\\/]|$)' -and $name -notmatch '[:/\x00]') 'An archive member path is unsafe.'
    }
    Require ($exact.Contains($Member) -and $exact.Contains('(attributes)') -and $exact.Contains('(listfile)')) 'Required archive members are absent.'
    return $names
}

function Require-SameNames([string[]]$Left, [string[]]$Right) {
    $set = [System.Collections.Generic.HashSet[string]]::new($Left, [System.StringComparer]::Ordinal)
    Require ($Left.Count -eq $Right.Count -and $set.SetEquals($Right)) 'The archive member identity set changed.'
}

function Directory-Manifest([string]$Root) {
    Require-NoLinks $Root
    $manifest = [ordered]@{}
    foreach ($item in @(Get-ChildItem -LiteralPath $Root -Force -Recurse)) { Require-NoLinks $item.FullName }
    foreach ($file in @(Get-ChildItem -LiteralPath $Root -Force -Recurse -File | Sort-Object FullName)) {
        $manifest[$file.FullName.Substring($Root.Length + 1)] = File-Hash $file.FullName
    }
    return $manifest
}

function Require-SameManifest($Left, $Right, [string]$Reason) {
    Require (($Left | ConvertTo-Json -Depth 12 -Compress) -ceq ($Right | ConvertTo-Json -Depth 12 -Compress)) $Reason
}

function Extraction-Manifest([string]$Root, [string[]]$Names) {
    Require-ArtifactPath $Root
    $manifest = Directory-Manifest $Root
    Require ($manifest.Count -eq 1406) 'Full extraction is incomplete or contains extra files.'
    Require-SameNames @($manifest.Keys) $Names
    $ordinary = @($Names | Where-Object { $_ -notin @('(attributes)', '(listfile)') })
    $listed = @($Utf8.GetString([System.IO.File]::ReadAllBytes((Join-Path $Root '(listfile)'))) -split '\r?\n' | Where-Object { $_ -ne '' })
    Require ($listed.Count -eq 1404) 'The archive listfile is incomplete.'
    Require-SameNames $ordinary $listed
    $attributes = [System.IO.File]::ReadAllBytes((Join-Path $Root '(attributes)'))
    Require ($attributes.Length -eq 39376 -and [System.BitConverter]::ToUInt32($attributes, 0) -eq 100 -and [System.BitConverter]::ToUInt32($attributes, 4) -eq 7) 'The version-100 CRC/time/MD5 attributes inventory changed.'
    return $manifest
}

function Protected-Snapshot([string]$Root, [bool]$IsStaging) {
    Require-NoLinks $Root $true
    $files = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -File | Where-Object { $_.Name -match '\.(exe|dll)(\.ORIGINAL)?$' })
    $files += @(Get-ChildItem -LiteralPath (Join-Path $Root 'Interface\AddOns') -Recurse -Force -File)
    $files += @(Get-Item -LiteralPath (Join-Path $Root 'Data\patch-T.MPQ'), (Join-Path $Root 'Data\patch-T.MPQ.ORIGINAL'))
    $protected = [ordered]@{}
    foreach ($file in @($files | Sort-Object FullName -Unique)) {
        Require-NoLinks $file.FullName $true
        $name = $file.FullName.Substring($Root.Length + 1)
        if ($IsStaging -and ($name -ceq $PrototypeName -or $name.StartsWith($HelperName + '\', [System.StringComparison]::Ordinal))) { continue }
        $protected[$name] = [ordered]@{ sha256 = File-Hash $file.FullName; bytes = $file.Length; mtimeUtcTicks = $file.LastWriteTimeUtc.Ticks }
    }
    $archives = @()
    foreach ($file in @(Get-ChildItem -LiteralPath (Join-Path $Root 'Data') -Recurse -Force -File | Where-Object { $_.Name -match '\.mpq($|\.)' } | Sort-Object FullName)) {
        if ($IsStaging -and $file.FullName -ceq $StagingArchive) { continue }
        Require-NoLinks $file.FullName $true
        $archives += [ordered]@{ name = $file.FullName.Substring($Root.Length + 1); bytes = $file.Length; mtimeUtcTicks = $file.LastWriteTimeUtc.Ticks }
    }
    return [ordered]@{ protectedFiles = $protected; otherMpqInventory = $archives; livePatchB = if ($IsStaging) { $null } else { File-Hash $LiveArchive } }
}

function Plain-Prototypes([byte[]]$Original, [string]$PatchPath) {
    $text = $Utf8.GetString($Original)
    $old = @'
function WeakAuras.GetRange(unit, checkVisible)
  -- LibRangeCheck's WotLK class tables do not know Ascension's custom
  -- Necromancer class. Prefer the actual Lichfrost spell range when it is
  -- available so range triggers do not remain permanently in standby.
  if unit == "target" and UnitExists(unit) and UnitCanAttack("player", unit) then
    local inRange = SpellRange.IsSpellInRange(501969, unit)
    if inRange == nil then
      inRange = SpellRange.IsSpellInRange(801722, unit)
    end
    if inRange == 1 then
      return 0, 30
    elseif inRange == 0 then
      return 30, 999
    end
  end
  return LibRangeCheck:GetRange(unit, checkVisible);
end
'@
    $old = $old.Replace("`r`n", "`n") + "`n"
    $new = "function WeakAuras.GetRange(unit, checkVisible)`n  return LibRangeCheck:GetRange(unit, checkVisible);`nend`n"
    $patch = $Utf8.GetString([System.IO.File]::ReadAllBytes($PatchPath)).Replace("`r`n", "`n")
    $lines = $patch -split "`n"
    Require ($lines[0] -ceq 'diff --git a/Prototypes.lua b/Prototypes.lua') 'The patch must target only Prototypes.lua.'
    Require (@($lines | Where-Object { $_ -match '^diff --git ' }).Count -eq 1 -and @($lines | Where-Object { $_ -match '^@@ ' }).Count -eq 1) 'The patch must contain exactly one file and one hunk.'
    Require (@($lines | Where-Object { $_ -ceq '--- a/Prototypes.lua' }).Count -eq 1 -and @($lines | Where-Object { $_ -ceq '+++ b/Prototypes.lua' }).Count -eq 1) 'The patch file paths changed.'
    $hunk = [Array]::FindIndex($lines, [Predicate[string]]{ param($line) $line -match '^@@ ' })
    $header = [regex]::Match($lines[$hunk], '^@@ -\d+,(\d+) \+\d+,(\d+) @@.*$')
    Require $header.Success 'The unified hunk header is unsupported.'
    $before = [System.Collections.Generic.List[string]]::new()
    $after = [System.Collections.Generic.List[string]]::new()
    foreach ($line in $lines[($hunk + 1)..($lines.Length - 1)]) {
        if ($line -eq '') { continue }
        Require ($line[0] -in @(' ', '-', '+')) 'Unsupported unified patch content.'
        if ($line[0] -ne '+') { $before.Add($line.Substring(1)) }
        if ($line[0] -ne '-') { $after.Add($line.Substring(1)) }
    }
    Require ($before.Count -eq [int]$header.Groups[1].Value -and $after.Count -eq [int]$header.Groups[2].Value) 'Unified hunk old/new line counts do not match its header.'
    $beforeText = ($before -join "`n") + "`n"
    $afterText = ($after -join "`n") + "`n"
    Require ($beforeText.Contains($old) -and $beforeText.IndexOf($old, [StringComparison]::Ordinal) -eq $beforeText.LastIndexOf($old, [StringComparison]::Ordinal)) 'The old range wrapper is absent or ambiguous in the patch.'
    Require ($afterText -ceq $beforeText.Replace($old, $new)) 'The patch changes more than the Lichfrost-only range wrapper.'
    $normalized = $text.Replace("`r`n", "`n")
    Require ($normalized.Contains($beforeText) -and $normalized.IndexOf($beforeText, [StringComparison]::Ordinal) -eq $normalized.LastIndexOf($beforeText, [StringComparison]::Ordinal)) 'The exact patch context is absent or ambiguous in the installed WeakAuras file.'
    $removedLines = ($old -split "`n")[1..14]
    $pattern = ($removedLines | ForEach-Object { [regex]::Escape($_) + '\r?\n' }) -join ''
    $segments = [regex]::Matches($text, $pattern)
    Require ($segments.Count -eq 1) 'The exact installed Lichfrost body is absent or ambiguous.'
    $modified = $text.Remove($segments[0].Index, $segments[0].Length)
    Require ($modified.Replace("`r`n", "`n") -ceq $normalized.Replace($old, $new)) 'Wrapper removal changed bytes outside the exact Lichfrost body.'
    return ,$Utf8.GetBytes($modified)
}

try {
    Require ($PSCommandPath -ceq (Join-Path $RepoRoot 'scripts\Install-CoARangeStaging.ps1')) 'Run the helper from its exact repository path.'
    $ArtifactDirectory = [System.IO.Path]::GetFullPath($ArtifactDirectory)
    Require ([System.IO.Directory]::GetParent($ArtifactDirectory).FullName -ceq $QaRoot) 'ArtifactDirectory must be a direct child of the fixed coa-range-20261003 QA directory.'
    Require ([System.IO.Path]::GetFileName($ArtifactDirectory) -match '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') 'Artifact directory name is unsafe.'
    foreach ($path in @($ArtifactDirectory, $LibraryInput, $PatchInput, $Tool)) { Require-NoLinks $path }
    foreach ($path in @($StagingRoot, $LiveRoot, $StagingArchive, $LiveArchive, $Prototype)) { Require-NoLinks $path $true }
    Require ((File-Hash $Tool) -eq $ToolHash -and (File-Hash $LiveArchive) -eq $LiveHash) 'The reviewed tool or production archive changed.'
    $Working = Join-Path $ArtifactDirectory 'patch-B.range.MPQ'
    $Rollback = Join-Path $ArtifactDirectory 'patch-B.rollback.MPQ'
    $PreparedPrototype = Join-Path $ArtifactDirectory 'Prototypes.prepared.lua'
    $RollbackPrototype = Join-Path $ArtifactDirectory 'Prototypes.rollback.lua'
    $RollbackHelper = Join-Path $ArtifactDirectory 'helper.rollback'
    $RetiredHelper = Join-Path $ArtifactDirectory 'helper.retired'
    $BeforeRoot = Join-Path $ArtifactDirectory 'before-extracted'
    $AfterRoot = Join-Path $ArtifactDirectory 'after-extracted'
    $ReportPath = Join-Path $ArtifactDirectory 'prepare.json'
    if ($PSCmdlet.ParameterSetName -eq 'Prepare') {
        Require ((File-Hash $StagingArchive) -eq $BaseHash) 'Staging archive is not the reviewed native-client baseline.'
        Require-NoLinks $Helper $true
        Require (-not (Test-Path -LiteralPath $ArtifactDirectory)) 'Choose a fresh artifact directory; prior evidence must be preserved.'
        $helperManifest = Directory-Manifest $Helper
        Require-SameNames @($helperManifest.Keys) @('COAWeakAurasRange.lua', 'COAWeakAurasRange.toc', 'README.md')
        $prototypeBytes = [System.IO.File]::ReadAllBytes($Prototype)
        $newPrototype = Plain-Prototypes $prototypeBytes $PatchInput
        $libraryHash = File-Hash $LibraryInput
        $patchHash = File-Hash $PatchInput
        $prototypeHash = File-Hash $Prototype
        $liveBefore = Protected-Snapshot $LiveRoot $false
        $stagingBefore = Protected-Snapshot $StagingRoot $true
        if (-not (Test-Path -LiteralPath $QaRoot)) { New-PrivateDirectory $QaRoot }
        New-PrivateDirectory $ArtifactDirectory
        $Allocated = $true
        $Phase = 'prepare-copy'
        Copy-Item -LiteralPath $StagingArchive -Destination $Rollback
        Copy-Item -LiteralPath $Rollback -Destination $Working
        Copy-Item -LiteralPath $Prototype -Destination $RollbackPrototype
        Copy-Item -LiteralPath $Helper -Destination $RollbackHelper -Recurse
        Copy-Item -LiteralPath $LibraryInput -Destination (Join-Path $ArtifactDirectory 'LibRangeCheck-2.0.lua')
        Copy-Item -LiteralPath $PatchInput -Destination (Join-Path $ArtifactDirectory 'WeakAuras-GetRange.patch')
        [System.IO.File]::WriteAllBytes($PreparedPrototype, $newPrototype)
        Require ((File-Hash $Rollback) -eq $BaseHash -and (File-Hash $Working) -eq $BaseHash -and (File-Hash $RollbackPrototype) -eq $prototypeHash) 'Rollback copies differ from their source files.'
        Require-SameManifest $helperManifest (Directory-Manifest $RollbackHelper) 'Helper rollback is incomplete.'
        $names = @(Archive-Names $Rollback)
        New-PrivateDirectory $BeforeRoot
        $null = Invoke-Mpq -Arguments @('extract', '--keep', '--output', $BeforeRoot, $Rollback)
        $beforeManifest = Extraction-Manifest $BeforeRoot $names
        Require ($beforeManifest[$Member] -eq $BaseMemberHash) 'The original native range-library member differs from the reviewed baseline.'
        $Phase = 'prepare-package'
        $null = Invoke-Mpq -Arguments @('add', '--overwrite', '--path', $Member, $Working, (Join-Path $ArtifactDirectory 'LibRangeCheck-2.0.lua'))
        $afterNames = @(Archive-Names $Working)
        Require-SameNames $names $afterNames
        New-PrivateDirectory $AfterRoot
        $null = Invoke-Mpq -Arguments @('extract', '--keep', '--output', $AfterRoot, $Working)
        $afterManifest = Extraction-Manifest $AfterRoot $afterNames
        $retained = 0
        foreach ($name in $names) {
            if ($name -ceq $Member) { Require ($afterManifest[$name] -eq $libraryHash) 'Packaged range-library bytes differ from the source.' }
            elseif ($name -notin @('(attributes)', '(listfile)')) { Require ($beforeManifest[$name] -eq $afterManifest[$name]) 'An unrelated archive member changed.'; $retained++ }
        }
        Require ($retained -eq 1403) 'All 1403 unrelated ordinary archive members must remain identical.'
        Require ((File-Hash $StagingArchive) -eq $BaseHash -and (File-Hash $Prototype) -eq $prototypeHash) 'Active staging inputs changed during preparation.'
        Require-SameManifest $helperManifest (Directory-Manifest $Helper) 'The active helper changed during preparation.'
        Require-SameManifest $liveBefore (Protected-Snapshot $LiveRoot $false) 'Protected production files changed during preparation.'
        Require-SameManifest $stagingBefore (Protected-Snapshot $StagingRoot $true) 'Unrelated staging files changed during preparation.'
        Write-NewReport 'archive-verified.json' ([ordered]@{ memberCount = 1406; unchangedOrdinaryMembers = 1403; beforeMemberSha256 = $beforeManifest; afterMemberSha256 = $afterManifest })
        Write-NewReport 'prepare.json' ([ordered]@{ schema = 1; status = 'prepared-not-installed'; preparedUtc = [DateTime]::UtcNow.ToString('o'); artifactDirectory = $ArtifactDirectory; scriptSha256 = File-Hash $PSCommandPath; baseArchiveSha256 = $BaseHash; liveArchiveSha256 = $LiveHash; toolSha256 = $ToolHash; librarySha256 = $libraryHash; patchSha256 = $patchHash; prototypeBeforeSha256 = $prototypeHash; prototypeAfterSha256 = File-Hash $PreparedPrototype; packagedArchiveSha256 = File-Hash $Working; archiveProofSha256 = File-Hash (Join-Path $ArtifactDirectory 'archive-verified.json'); helperManifest = $helperManifest; liveProtected = $liveBefore; stagingProtected = $stagingBefore; clientLaunched = $false; installed = $false })
        $recovery = "Keep this directory intact. Close every game client before recovery. Restore patch-B.rollback.MPQ to $StagingArchive and Prototypes.rollback.lua to $Prototype. If the helper was retired, restore helper.retired (or the identical helper.rollback copy) to $Helper only after checking that the destination is absent. Do not overwrite an unexpected directory or replay this installer after a partial failure. No automatic rollback is performed. Production files and servers are never part of this operation.`n"
        [System.IO.File]::WriteAllText((Join-Path $ArtifactDirectory 'RECOVERY.txt'), $recovery, $Utf8)
        Write-Host 'Staging range update prepared and verified. No active client files were changed; close every client before -Install.'
    }
    else {
        Require-GameClosed
        Require (Test-Path -LiteralPath $ReportPath) 'Prepare a fresh verified artifact directory first.'
        Require (-not (Test-Path -LiteralPath (Join-Path $ArtifactDirectory 'prepare-failed.json')) -and (Test-Path -LiteralPath (Join-Path $ArtifactDirectory 'RECOVERY.txt'))) 'Preparation did not finish cleanly; preserve its evidence and choose a fresh artifact directory.'
        Require (-not (Test-Path -LiteralPath (Join-Path $ArtifactDirectory 'install-report.json')) -and -not (Test-Path -LiteralPath (Join-Path $ArtifactDirectory 'install-failed.json')) -and -not (Test-Path -LiteralPath $RetiredHelper)) 'Installation evidence already exists; do not replay this operation.'
        $Allocated = $true
        $proof = Get-Content -Raw -LiteralPath $ReportPath | ConvertFrom-Json
        Require ($proof.schema -eq 1 -and $proof.status -ceq 'prepared-not-installed' -and $proof.artifactDirectory -ceq $ArtifactDirectory) 'Preparation report identity is invalid.'
        Require ($proof.scriptSha256 -eq (File-Hash $PSCommandPath) -and $proof.baseArchiveSha256 -eq $BaseHash -and $proof.liveArchiveSha256 -eq $LiveHash -and $proof.toolSha256 -eq $ToolHash) 'Preparation constants or installer changed.'
        foreach ($path in @($Working, $Rollback, $PreparedPrototype, $RollbackPrototype, $RollbackHelper, $BeforeRoot, $AfterRoot)) { Require-ArtifactPath $path }
        Require ((File-Hash $Working) -eq $proof.packagedArchiveSha256 -and (File-Hash $Rollback) -eq $BaseHash -and (File-Hash $StagingArchive) -eq $BaseHash) 'The prepared or active archive changed.'
        Require ((File-Hash $Prototype) -eq $proof.prototypeBeforeSha256 -and (File-Hash $RollbackPrototype) -eq $proof.prototypeBeforeSha256 -and (File-Hash $PreparedPrototype) -eq $proof.prototypeAfterSha256) 'The prepared or active WeakAuras file changed.'
        Require ((File-Hash $LibraryInput) -eq $proof.librarySha256 -and (File-Hash (Join-Path $ArtifactDirectory 'LibRangeCheck-2.0.lua')) -eq $proof.librarySha256 -and (File-Hash $PatchInput) -eq $proof.patchSha256 -and (File-Hash (Join-Path $ArtifactDirectory 'WeakAuras-GetRange.patch')) -eq $proof.patchSha256) 'Reviewed range-update source inputs changed.'
        Require ((File-Hash (Join-Path $ArtifactDirectory 'archive-verified.json')) -eq $proof.archiveProofSha256) 'Archive verification evidence changed.'
        $archiveProof = Get-Content -Raw -LiteralPath (Join-Path $ArtifactDirectory 'archive-verified.json') | ConvertFrom-Json
        Require ($archiveProof.memberCount -eq 1406 -and $archiveProof.unchangedOrdinaryMembers -eq 1403) 'Archive verification scope is incomplete.'
        Require ($archiveProof.beforeMemberSha256.PSObject.Properties[$Member].Value -eq $BaseMemberHash) 'Original native-member hash evidence changed.'
        $names = @(Archive-Names $Rollback)
        Require-SameNames $names @(Archive-Names $Working)
        Require-SameManifest $archiveProof.beforeMemberSha256 (Extraction-Manifest $BeforeRoot $names) 'Original extraction evidence changed.'
        Require-SameManifest $archiveProof.afterMemberSha256 (Extraction-Manifest $AfterRoot $names) 'Prepared extraction evidence changed.'
        Require-NoLinks $Helper $true
        Require-SameManifest $proof.helperManifest (Directory-Manifest $Helper) 'The active helper changed after preparation.'
        Require-SameManifest $proof.helperManifest (Directory-Manifest $RollbackHelper) 'Helper rollback changed after preparation.'
        Require-SameManifest $proof.liveProtected (Protected-Snapshot $LiveRoot $false) 'Protected production files changed after preparation.'
        Require-SameManifest $proof.stagingProtected (Protected-Snapshot $StagingRoot $true) 'Unrelated staging files changed after preparation.'
        Require-GameClosed
        $Phase = 'install-archive'
        $InstallAttempted = $true
        Copy-Item -LiteralPath $Working -Destination $StagingArchive -Force
        Require ((File-Hash $StagingArchive) -eq $proof.packagedArchiveSha256) 'Staging archive copy is incomplete.'
        Require-GameClosed
        $Phase = 'install-prototypes'
        Copy-Item -LiteralPath $PreparedPrototype -Destination $Prototype -Force
        Require ((File-Hash $Prototype) -eq $proof.prototypeAfterSha256) 'WeakAuras copy is incomplete.'
        Require-GameClosed
        $Phase = 'retire-helper'
        Require ([System.IO.Path]::GetFullPath($Helper) -ceq (Join-Path $StagingRoot $HelperName)) 'The helper move source escaped staging.'
        Require-ArtifactPath $RetiredHelper
        Require (-not (Test-Path -LiteralPath $RetiredHelper)) 'The retired-helper destination already exists.'
        Move-Item -LiteralPath $Helper -Destination $RetiredHelper
        Require (-not (Test-Path -LiteralPath $Helper)) 'The old helper remains active.'
        Require-SameManifest $proof.helperManifest (Directory-Manifest $RetiredHelper) 'The retired helper is incomplete.'
        Require-GameClosed
        $Phase = 'verify-install'
        Require-SameManifest $proof.liveProtected (Protected-Snapshot $LiveRoot $false) 'Protected production files changed during installation.'
        Require-SameManifest $proof.stagingProtected (Protected-Snapshot $StagingRoot $true) 'Unrelated staging files changed during installation.'
        Require ((File-Hash $StagingArchive) -eq $proof.packagedArchiveSha256 -and (File-Hash $Prototype) -eq $proof.prototypeAfterSha256 -and (File-Hash $Rollback) -eq $BaseHash -and (File-Hash $LiveArchive) -eq $LiveHash) 'Final active or rollback file hashes changed.'
        Write-NewReport 'install-report.json' ([ordered]@{ status = 'staging-range-library-installed-helper-retired'; completedUtc = [DateTime]::UtcNow.ToString('o'); prepareSha256 = File-Hash $ReportPath; stagedArchiveSha256 = File-Hash $StagingArchive; stagedPrototypeSha256 = File-Hash $Prototype; rollbackArchiveSha256 = File-Hash $Rollback; rollbackPrototypeSha256 = File-Hash $RollbackPrototype; retiredHelper = $RetiredHelper; memberCount = 1406; unchangedOrdinaryMembers = 1403; protectedFilesUnchanged = $true; productionUnchanged = $true; clientLaunched = $false; gameplayVerified = $false; automaticRollbackPerformed = $false })
        Write-Host 'Staging-only range library installed; WeakAuras restored to the plain wrapper and the old helper retained outside AddOns. No client was launched.'
    }
}
catch {
    if ($Allocated) {
        $failureName = if ($PSCmdlet.ParameterSetName -eq 'Install') { 'install-failed.json' } else { 'prepare-failed.json' }
        if (-not (Test-Path -LiteralPath (Join-Path $ArtifactDirectory $failureName))) {
            Write-NewReport $failureName ([ordered]@{ status = 'failed-evidence-retained'; phase = $Phase; failedUtc = [DateTime]::UtcNow.ToString('o'); installAttempted = $InstallAttempted; failure = $_.Exception.Message; automaticRollbackPerformed = $false; clientLaunched = $false; recoveryInstructions = 'Close every client and review RECOVERY.txt plus the exact rollback files. Do not replay this artifact directory or overwrite unexpected files.' })
        }
    }
    throw
}
