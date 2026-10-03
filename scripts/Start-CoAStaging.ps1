param(
  [string]$ClientDirectory = 'C:\Games\Ascension-WOW-Staging',
  [string]$AuthEndpoint = '127.0.0.1:33725',
  [switch]$Candidate,
  [switch]$RestoreConnection
)

$ErrorActionPreference = 'Stop'

function Get-StagingConnection {
  param([string]$Directory, [AllowNull()][object]$Endpoint, [switch]$Candidate)
  $port = 33725
  $realm = 'COA G1 STAGING'
  if ($Candidate) {
    if (-not [IO.Path]::IsPathRooted($Directory) -or
        -not [string]::Equals([IO.Path]::GetFullPath($Directory).TrimEnd('\', '/'),
                             'C:\Games\Ascension-WOW-Staging', [StringComparison]::OrdinalIgnoreCase)) {
      throw 'Candidate mode requires the separate C:\Games\Ascension-WOW-Staging client.'
    }
    $port = 33726
    $realm = 'COA G1 CANDIDATE'
  }
  $expectedEndpoint = '127.0.0.1:' + $port
  if ($null -ne $Endpoint -and ($Endpoint -isnot [string] -or $Endpoint -cne $expectedEndpoint)) {
    throw 'This mode only supports its fixed isolated local login endpoint.'
  }
  return [pscustomobject]@{ Endpoint = $expectedEndpoint; Port = $port; Realm = $realm }
}

function Set-ClientSetting {
  param([string]$Text, [string]$Name, [AllowNull()][object]$Value)
  if ($null -ne $Value -and ($Value -isnot [string] -or $Value -match '["\r\n]')) {
    throw 'The saved connection setting is not a valid client string.'
  }
  $pattern = '(?im)^[ \t]*SET[ \t]+' + [regex]::Escape($Name) + '(?:[ \t]+[^\r\n]*)?(?:\r?\n|$)'
  $withoutSetting = [regex]::Replace($Text, $pattern, '')
  if ($null -eq $Value) { return $withoutSetting }
  if ($withoutSetting.Length -gt 0 -and -not $withoutSetting.EndsWith("`n")) {
    $withoutSetting += "`r`n"
  }
  return $withoutSetting + 'SET ' + $Name + ' "' + $Value + '"' + "`r`n"
}

function Get-ClientSetting {
  param([string]$Text, [string]$Name)
  $pattern = '(?im)^[ \t]*SET[ \t]+' + [regex]::Escape($Name) + '[ \t]+"([^"\r\n]*)"'
  $matches = [regex]::Matches($Text, $pattern)
  if ($matches.Count -gt 0) { return $matches[$matches.Count - 1].Groups[1].Value }
  return $null
}

function Assert-PlainPath {
  param([string]$Path)
  $item = Get-Item -LiteralPath $Path -Force
  while ($null -ne $item) {
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
      throw 'Linked client paths are not supported by this connection helper.'
    }
    if ($item -is [IO.FileInfo]) { $item = $item.Directory } else { $item = $item.Parent }
  }
}

function Get-ClientPaths {
  param([string]$Directory, [switch]$RequireExecutable)
  $resolved = Resolve-Path -LiteralPath $Directory
  if ($resolved.Provider.Name -ne 'FileSystem' -or -not (Test-Path -LiteralPath $resolved.Path -PathType Container)) {
    throw 'The client directory must be an existing local directory.'
  }
  $client = [IO.Path]::GetFullPath($resolved.Path).TrimEnd('\', '/')
  Assert-PlainPath $client
  $paths = [pscustomobject]@{
    Client = $client
    Executable = Join-Path $client 'Ascension.exe'
    Config = Join-Path $client 'WTF\Config.wtf'
    RealmList = Join-Path $client 'Data\enUS\realmlist.wtf'
    StateDirectory = Join-Path $client 'coa-staging-connection'
    RecoveryFile = Join-Path $client 'coa-staging-connection\connection-recovery.json'
  }
  $requiredFiles = @($paths.Config, $paths.RealmList)
  if ($RequireExecutable) { $requiredFiles += $paths.Executable }
  foreach ($path in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required client file is missing: $path" }
    Assert-PlainPath $path
  }
  if (Test-Path -LiteralPath $paths.StateDirectory) {
    if (-not (Test-Path -LiteralPath $paths.StateDirectory -PathType Container)) {
      throw 'The connection recovery directory is not a directory.'
    }
    Assert-PlainPath $paths.StateDirectory
  }
  return $paths
}

function Get-BytesHash {
  param([byte[]]$Bytes)
  $hash = [Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($hash.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
  finally { $hash.Dispose() }
}

function Test-RecoveryState {
  param([object]$State, [string]$Client)
  if ($null -eq $State) { throw 'The saved connection recovery data is empty.' }
  foreach ($property in @('Version', 'ClientDirectory', 'ConfigEndpoint', 'ConfigRealm', 'RealmListBytes', 'RealmListSha256')) {
    if ($null -eq $State.PSObject.Properties[$property]) { throw 'The saved connection recovery data is incomplete.' }
  }
  if ($State.Version -ne 1 -or $State.ClientDirectory -isnot [string] -or
      -not [IO.Path]::IsPathRooted($State.ClientDirectory) -or
      -not [string]::Equals([IO.Path]::GetFullPath($State.ClientDirectory).TrimEnd('\', '/'), $Client, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The saved connection recovery belongs to a different client path or unsupported version.'
  }
  foreach ($value in @($State.ConfigEndpoint, $State.ConfigRealm)) {
    if ($null -ne $value -and ($value -isnot [string] -or $value.Length -gt 4096 -or $value -match '["\r\n]')) {
      throw 'The saved connection recovery setting is invalid.'
    }
  }
  if ($State.RealmListBytes -isnot [string] -or $State.RealmListBytes.Length -gt 1398104 -or
      $State.RealmListSha256 -isnot [string] -or $State.RealmListSha256 -cnotmatch '^[0-9a-f]{64}$') {
    throw 'The saved realm-list recovery data is invalid.'
  }
  try { $bytes = [Convert]::FromBase64String($State.RealmListBytes) }
  catch { throw 'The saved realm-list recovery data is not valid base64.' }
  if ((Get-BytesHash $bytes) -cne $State.RealmListSha256) { throw 'The saved realm-list recovery checksum does not match.' }
  return $State
}

function Read-ConnectionRecovery {
  param([object]$Paths)
  if (-not (Test-Path -LiteralPath $Paths.RecoveryFile -PathType Leaf)) {
    throw 'No saved staging connection was found for this client.'
  }
  Assert-PlainPath $Paths.RecoveryFile
  if ((Get-Item -LiteralPath $Paths.RecoveryFile).Length -gt 2097152) {
    throw 'The saved connection recovery file is unexpectedly large.'
  }
  $state = [IO.File]::ReadAllText($Paths.RecoveryFile) | ConvertFrom-Json
  return Test-RecoveryState $state $Paths.Client
}

function Save-ConnectionRecovery {
  param([object]$Paths, [AllowNull()][object]$Endpoint, [AllowNull()][object]$Realm, [byte[]]$RealmListBytes)
  if (-not (Test-Path -LiteralPath $Paths.StateDirectory)) {
    New-Item -ItemType Directory -Path $Paths.StateDirectory | Out-Null
  }
  Assert-PlainPath $Paths.StateDirectory
  $state = [pscustomobject]@{
    Version = 1
    ClientDirectory = $Paths.Client
    ConfigEndpoint = $Endpoint
    ConfigRealm = $Realm
    RealmListBytes = [Convert]::ToBase64String($RealmListBytes)
    RealmListSha256 = Get-BytesHash $RealmListBytes
  }
  $null = Test-RecoveryState $state $Paths.Client
  $utf8 = New-Object Text.UTF8Encoding($false)
  $bytes = $utf8.GetBytes(($state | ConvertTo-Json))
  # Publish the completed file without overwriting recovery from a concurrent launch.
  $temporaryFile = Join-Path $Paths.StateDirectory ('.connection-' + [Guid]::NewGuid().ToString('N') + '.tmp')
  try {
    $stream = [IO.File]::Open($temporaryFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    [IO.File]::Move($temporaryFile, $Paths.RecoveryFile)
  } finally {
    if ([IO.File]::Exists($temporaryFile)) { [IO.File]::Delete($temporaryFile) }
  }
}

function Restore-ClientConnection {
  param([object]$Paths)
  if (Get-Process -Name Ascension -ErrorAction SilentlyContinue) {
    throw 'Close the game, then run this helper with -RestoreConnection to restore the saved connection.'
  }
  # Revalidate paths and saved data before writing; an interrupted launch may be recovered later.
  $checkedPaths = Get-ClientPaths $Paths.Client
  $state = Read-ConnectionRecovery $checkedPaths
  $utf8 = New-Object Text.UTF8Encoding($false)
  $currentConfig = [IO.File]::ReadAllText($checkedPaths.Config)
  $restored = Set-ClientSetting $currentConfig 'realmList' $state.ConfigEndpoint
  $restored = Set-ClientSetting $restored 'realmName' $state.ConfigRealm
  [IO.File]::WriteAllText($checkedPaths.Config, $restored, $utf8)
  [IO.File]::WriteAllBytes($checkedPaths.RealmList, [Convert]::FromBase64String($state.RealmListBytes))
  $verifiedConfig = [IO.File]::ReadAllText($checkedPaths.Config)
  if ((Get-ClientSetting $verifiedConfig 'realmList') -cne $state.ConfigEndpoint -or
      (Get-ClientSetting $verifiedConfig 'realmName') -cne $state.ConfigRealm -or
      (Get-BytesHash ([IO.File]::ReadAllBytes($checkedPaths.RealmList))) -cne $state.RealmListSha256) {
    throw 'Connection restoration could not be verified; the recovery file has been retained.'
  }
  Remove-Item -LiteralPath $checkedPaths.RecoveryFile
}

function Copy-StagingProfiles {
  param([string]$Client, [switch]$Candidate)
  $accountRoot = Join-Path $Client 'WTF\Account'
  if (-not (Test-Path -LiteralPath $accountRoot)) { return }
  Assert-PlainPath $accountRoot
  foreach ($account in Get-ChildItem -LiteralPath $accountRoot -Directory) {
    Assert-PlainPath $account.FullName
    $sourceNames = @('AzerothCore')
    $profileName = 'COA G1 STAGING'
    if ($Candidate) { $sourceNames = @('COA G1 STAGING', 'AzerothCore'); $profileName = 'COA G1 CANDIDATE' }
    $stageProfile = Join-Path $account.FullName $profileName
    if (Test-Path -LiteralPath $stageProfile) { continue }
    foreach ($sourceName in $sourceNames) {
      $sourceProfile = Join-Path $account.FullName $sourceName
      if (-not (Test-Path -LiteralPath $sourceProfile -PathType Container)) { continue }
      Assert-PlainPath $sourceProfile
      if (Get-ChildItem -LiteralPath $sourceProfile -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) {
        throw 'Linked profile files are not supported by this connection helper.'
      }
      Copy-Item -LiteralPath $sourceProfile -Destination $stageProfile -Recurse
      break
    }
  }
}

try {
  $endpointOverride = $null
  if ($PSBoundParameters.ContainsKey('AuthEndpoint')) { $endpointOverride = $AuthEndpoint }
  $connectionSettings = Get-StagingConnection $ClientDirectory $endpointOverride -Candidate:$Candidate
  $paths = Get-ClientPaths $ClientDirectory -RequireExecutable:(-not $RestoreConnection)
  if (Get-Process -Name Ascension -ErrorAction SilentlyContinue) {
    throw 'Please close the game before changing its connection.'
  }
  if ($RestoreConnection) {
    Restore-ClientConnection $paths
    Write-Host 'The original client connection has been restored. No game was launched.'
    exit 0
  }
  if (Test-Path -LiteralPath $paths.RecoveryFile) {
    throw 'An earlier staging connection did not finish cleanup. Close the game and run this helper with -RestoreConnection before launching again.'
  }
  $probe = New-Object Net.Sockets.TcpClient
  try {
    $connection = $probe.BeginConnect('127.0.0.1', $connectionSettings.Port, $null, $null)
    if (-not $connection.AsyncWaitHandle.WaitOne(3000)) { throw 'The staging login server is not reachable.' }
    $probe.EndConnect($connection)
  } finally {
    $probe.Dispose()
  }

  $originalConfig = [IO.File]::ReadAllText($paths.Config)
  $originalEndpoint = Get-ClientSetting $originalConfig 'realmList'
  $originalRealm = Get-ClientSetting $originalConfig 'realmName'
  $originalRealmList = [IO.File]::ReadAllBytes($paths.RealmList)
  Save-ConnectionRecovery $paths $originalEndpoint $originalRealm $originalRealmList

  try {
    # Profile copying is inside the recovery guard, including its failure path.
    Copy-StagingProfiles $paths.Client -Candidate:$Candidate
    $utf8 = New-Object Text.UTF8Encoding($false)
    $stageConfig = Set-ClientSetting $originalConfig 'realmList' $connectionSettings.Endpoint
    $stageConfig = Set-ClientSetting $stageConfig 'realmName' $connectionSettings.Realm
    [IO.File]::WriteAllText($paths.Config, $stageConfig, $utf8)
    [IO.File]::WriteAllText($paths.RealmList, ('set realmlist ' + $connectionSettings.Endpoint + "`r`n"), $utf8)
    $game = Start-Process -FilePath $paths.Executable -WorkingDirectory $paths.Client -WindowStyle Normal -PassThru
    $game.WaitForExit()
  } finally {
    Restore-ClientConnection $paths
  }
} catch {
  Add-Type -AssemblyName System.Windows.Forms
  [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'COA staging connection') | Out-Null
  exit 1
}
