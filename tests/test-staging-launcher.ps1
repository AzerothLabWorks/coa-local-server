param([string]$Launcher = (Join-Path $PSScriptRoot '..\scripts\Start-CoAStaging.ps1'))

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $Launcher).Path, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'The staging launcher has PowerShell parse errors.' }
# Only function definitions are imported. The launcher body, network probe and game launch never run.
$definitions = @($ast.EndBlock.Statements | Where-Object { $_ -is [Management.Automation.Language.FunctionDefinitionAst] })
Invoke-Expression (($definitions | ForEach-Object { $_.Extent.Text }) -join "`n")

$script:Checks = 0
$script:FakeGameRunning = $false
$script:FailProfileCopy = $false
function Assert-Test {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw $Message }
  $script:Checks++
}
function Assert-Throws {
  param([scriptblock]$Action, [string]$Message)
  $threw = $false
  try { $null = & $Action } catch { $threw = $true }
  Assert-Test $threw $Message
}
# Stub all game-process interactions; tests operate solely on synthetic temporary files.
function Get-Process {
  param([string]$Name, [object]$ErrorAction)
  if ($script:FakeGameRunning) { return [pscustomobject]@{ ProcessName = 'Ascension' } }
}
function Start-Process { throw 'Game launching is forbidden in this test.' }
function Copy-Item {
  param([string]$LiteralPath, [string]$Destination, [switch]$Recurse)
  if ($script:FailProfileCopy) { throw 'Injected profile copy failure' }
  Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Recurse:$Recurse
}

$utf8 = New-Object Text.UTF8Encoding($false)
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
$fixtureName = 'coa-staging-launcher-test-' + [Guid]::NewGuid().ToString('N')
$fixtureRoot = Join-Path $tempBase $fixtureName
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
function New-Fixture {
  param([string]$Name, [string]$ConfigText)
  $clientFixture = Join-Path $fixtureRoot $Name
  New-Item -ItemType Directory -Path (Join-Path $clientFixture 'WTF'), (Join-Path $clientFixture 'Data\enUS') | Out-Null
  [IO.File]::WriteAllText((Join-Path $clientFixture 'WTF\Config.wtf'), $ConfigText, $utf8)
  [IO.File]::WriteAllBytes((Join-Path $clientFixture 'Data\enUS\realmlist.wtf'), [byte[]]@(239, 187, 191, 115, 101, 116, 32, 114, 101, 97, 108, 109, 108, 105, 115, 116, 32, 108, 105, 118, 101, 13, 10))
  return Get-ClientPaths $clientFixture
}

try {
  $Candidate = $false
  $baselineConnection = Get-StagingConnection 'C:\Games\Ascension-WOW-Staging' $null
  Assert-Test ($baselineConnection.Endpoint -ceq '127.0.0.1:33725' -and $baselineConnection.Port -eq 33725) 'The default must retain the baseline staging endpoint.'
  Assert-Test ($baselineConnection.Realm -ceq 'COA G1 STAGING') 'The default must retain the baseline realm.'
  $candidateConnection = Get-StagingConnection 'C:\Games\Ascension-WOW-Staging' $null -Candidate
  Assert-Test ($candidateConnection.Endpoint -ceq '127.0.0.1:33726' -and $candidateConnection.Port -eq 33726) 'Candidate mode must select only the candidate endpoint.'
  Assert-Test ($candidateConnection.Realm -ceq 'COA G1 CANDIDATE') 'Candidate mode must select the fixed candidate realm.'
  Assert-Test ((Get-StagingConnection 'C:\Games\Ascension-WOW-Staging' '127.0.0.1:33726' -Candidate).Endpoint -ceq '127.0.0.1:33726') 'The exact explicit candidate endpoint should be accepted.'
  Assert-Test ((Get-StagingConnection 'c:\games\Ascension-WOW-Staging\' $null -Candidate).Realm -ceq 'COA G1 CANDIDATE') 'Equivalent case and trailing separator must retain the exact staging client boundary.'
  Assert-Throws { Get-StagingConnection 'C:\Games\Ascension-WOW' $null -Candidate } 'Candidate mode must reject the production client.'
  Assert-Throws { Get-StagingConnection 'C:\Games\Ascension-WOW-Staging-Other' $null -Candidate } 'A similar client name must not satisfy the candidate boundary.'
  Assert-Throws { Get-StagingConnection 'C:\Games\Ascension-WOW-Staging\nested' $null -Candidate } 'A child directory must not satisfy the exact candidate client boundary.'
  Assert-Throws { Get-StagingConnection 'Ascension-WOW-Staging' $null -Candidate } 'Candidate mode must reject relative client paths.'
  foreach ($endpoint in @('127.0.0.1:33724', '127.0.0.1:33725', 'localhost:33726', '192.0.2.1:33726', '', "127.0.0.1:33726`n")) {
    Assert-Throws { Get-StagingConnection 'C:\Games\Ascension-WOW-Staging' $endpoint -Candidate } 'Candidate mode must reject arbitrary or other-server endpoints.'
  }
  Assert-Throws { Get-StagingConnection 'C:\Games\Ascension-WOW-Staging' '127.0.0.1:33726' } 'The candidate endpoint requires the explicit candidate switch.'
  $endpointParameter = @($ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -ceq 'AuthEndpoint' })
  Assert-Test ($endpointParameter.Count -eq 1 -and $endpointParameter[0].DefaultValue.SafeGetValue() -ceq '127.0.0.1:33725') 'The public endpoint parameter default must remain backward compatible.'
  Assert-Test (@($ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -ceq 'Candidate' }).Count -eq 1) 'Candidate mode must be an explicit launcher parameter.'

  $plain = "SET gxResolution `"1920x1080`"`r`n"
  Assert-Test ($null -eq (Get-ClientSetting $plain 'realmList')) 'Absent settings must remain null.'
  Assert-Test ((Set-ClientSetting $plain 'realmList' $null) -ceq $plain) 'Null must remove or retain an absent setting, not append an empty string.'
  $emptySetting = Set-ClientSetting $plain 'realmList' ''
  Assert-Test ((Get-ClientSetting $emptySetting 'realmList') -ceq '') 'An explicitly empty setting differs from an absent setting.'
  Assert-Test ((Set-ClientSetting $emptySetting 'realmList' $null) -ceq $plain) 'Restoring null must remove the temporary setting.'
  $duplicates = "SET realmList `"one`"`nSET realmList `"two`"`n" + $plain
  $oneSetting = Set-ClientSetting $duplicates 'realmList' 'original'
  Assert-Test (([regex]::Matches($oneSetting, '(?im)^SET realmList ').Count) -eq 1) 'A connection change must not leave conflicting duplicate entries.'
  Assert-Test ($oneSetting.Contains($plain)) 'Unrelated client settings must remain unchanged.'
  Assert-Test ((Get-ClientSetting $duplicates 'realmList') -ceq 'two') 'Reading duplicate settings must retain the last effective value.'
  $bareSetting = "SET realmList`r`n" + $plain
  Assert-Test ((Set-ClientSetting $bareSetting 'realmList' $null) -ceq $plain) 'Removing a malformed connection line must not consume the next client setting.'
  Assert-Throws { Set-ClientSetting $plain 'realmList' "bad`nSET accountName secret" } 'Newline injection must be rejected.'
  Assert-Throws { Set-ClientSetting $plain 'realmList' 42 } 'Non-string saved settings must be rejected.'

  $paths = New-Fixture 'absent-settings' $plain
  Assert-Throws { Get-ClientPaths $paths.Client -RequireExecutable } 'Normal launching requires the game executable.'
  $originalBytes = [IO.File]::ReadAllBytes($paths.RealmList)
  Save-ConnectionRecovery $paths $null $null $originalBytes
  $saved = Read-ConnectionRecovery $paths
  Assert-Test ($null -eq $saved.ConfigEndpoint -and $null -eq $saved.ConfigRealm) 'JSON recovery must retain both absent settings.'
  $savedFileHash = Get-BytesHash ([IO.File]::ReadAllBytes($paths.RecoveryFile))
  Assert-Throws { Save-ConnectionRecovery $paths 'replacement' 'replacement' $originalBytes } 'A concurrent launch must not replace recovery data.'
  Assert-Test ((Get-BytesHash ([IO.File]::ReadAllBytes($paths.RecoveryFile))) -ceq $savedFileHash) 'Original recovery data must remain intact.'
  Assert-Test (@(Get-ChildItem -LiteralPath $paths.StateDirectory -Filter '*.tmp' -Force).Count -eq 0) 'A refused concurrent save must not leave a partial recovery file.'
  $changed = Set-ClientSetting $plain 'realmList' '127.0.0.1:33725'
  $changed = Set-ClientSetting $changed 'realmName' 'COA G1 STAGING'
  $changed += "SET Sound_EnableAllSound `"0`"`r`n"
  [IO.File]::WriteAllText($paths.Config, $changed, $utf8)
  [IO.File]::WriteAllText($paths.RealmList, 'set realmlist 127.0.0.1:33725', $utf8)
  Restore-ClientConnection $paths
  $restored = [IO.File]::ReadAllText($paths.Config)
  Assert-Test ($null -eq (Get-ClientSetting $restored 'realmList') -and $null -eq (Get-ClientSetting $restored 'realmName')) 'Restore must preserve originally absent settings.'
  Assert-Test ($restored.Contains('SET Sound_EnableAllSound "0"')) 'Settings changed while playing must survive connection restoration.'
  Assert-Test ((Get-BytesHash ([IO.File]::ReadAllBytes($paths.RealmList))) -ceq (Get-BytesHash $originalBytes)) 'Realm-list bytes including encoding must be restored exactly.'
  Assert-Test (-not (Test-Path -LiteralPath $paths.RecoveryFile)) 'Successful restoration must remove the recovery marker.'

  $originalConfig = "SET realmList `"127.0.0.1:33724`"`r`nSET realmName `"AzerothCore`"`r`n" + $plain
  $paths = New-Fixture 'saved-settings' $originalConfig
  $originalBytes = [IO.File]::ReadAllBytes($paths.RealmList)
  Save-ConnectionRecovery $paths '127.0.0.1:33724' 'AzerothCore' $originalBytes
  $saved = Read-ConnectionRecovery $paths
  $wrongPath = $saved | ConvertTo-Json | ConvertFrom-Json
  $wrongPath.ClientDirectory = Join-Path $fixtureRoot 'different-client'
  Assert-Throws { Test-RecoveryState $wrongPath $paths.Client } 'Recovery for another client path must be rejected.'
  $badChecksum = $saved | ConvertTo-Json | ConvertFrom-Json
  $badChecksum.RealmListSha256 = '0' * 64
  Assert-Throws { Test-RecoveryState $badChecksum $paths.Client } 'Damaged recovery bytes must be rejected.'
  $badEncoding = $saved | ConvertTo-Json | ConvertFrom-Json
  $badEncoding.RealmListBytes = '*invalid*'
  Assert-Throws { Test-RecoveryState $badEncoding $paths.Client } 'Invalid base64 must be rejected.'
  Assert-Throws { Test-RecoveryState ([pscustomobject]@{ Version = 1 }) $paths.Client } 'Incomplete recovery metadata must be rejected.'
  $script:FakeGameRunning = $true
  Assert-Throws { Restore-ClientConnection $paths } 'Restoration must refuse while a game is running.'
  Assert-Test (Test-Path -LiteralPath $paths.RecoveryFile) 'Refusing restoration must retain recovery data.'
  Assert-Test ([IO.File]::ReadAllText($paths.Config) -ceq $originalConfig) 'Refusing restoration must not change client files.'
  $script:FakeGameRunning = $false
  Restore-ClientConnection $paths
  Assert-Test ((Get-ClientSetting ([IO.File]::ReadAllText($paths.Config)) 'realmList') -ceq '127.0.0.1:33724') 'The original login endpoint must be restored.'
  Assert-Test ((Get-ClientSetting ([IO.File]::ReadAllText($paths.Config)) 'realmName') -ceq 'AzerothCore') 'The original realm name must be restored.'

  $emptyConfig = "SET realmList `"`"`r`nSET realmName `"`"`r`n" + $plain
  $paths = New-Fixture 'empty-settings' $emptyConfig
  Save-ConnectionRecovery $paths '' '' ([IO.File]::ReadAllBytes($paths.RealmList))
  [IO.File]::WriteAllText($paths.Config, (Set-ClientSetting (Set-ClientSetting $emptyConfig 'realmList' 'stage') 'realmName' 'stage'), $utf8)
  Restore-ClientConnection $paths
  Assert-Test ((Get-ClientSetting ([IO.File]::ReadAllText($paths.Config)) 'realmList') -ceq '') 'JSON restoration must retain an explicitly empty endpoint.'
  Assert-Test ((Get-ClientSetting ([IO.File]::ReadAllText($paths.Config)) 'realmName') -ceq '') 'JSON restoration must retain an explicitly empty realm name.'

  $paths = New-Fixture 'damaged-recovery' $plain
  Save-ConnectionRecovery $paths $null $null ([IO.File]::ReadAllBytes($paths.RealmList))
  $damaged = Read-ConnectionRecovery $paths
  $damaged.ClientDirectory = Join-Path $fixtureRoot 'another-client'
  [IO.File]::WriteAllText($paths.RecoveryFile, ($damaged | ConvertTo-Json), $utf8)
  Assert-Throws { Restore-ClientConnection $paths } 'An on-disk recovery for another client must not be applied.'
  Assert-Test ([IO.File]::ReadAllText($paths.Config) -ceq $plain) 'Invalid on-disk recovery must not write client settings.'
  Assert-Test (Test-Path -LiteralPath $paths.RecoveryFile) 'Invalid recovery must remain available for manual diagnosis.'

  $paths = New-Fixture 'profile-failure' $plain
  $liveProfile = Join-Path $paths.Client 'WTF\Account\synthetic-account\AzerothCore'
  New-Item -ItemType Directory -Path $liveProfile | Out-Null
  [IO.File]::WriteAllText((Join-Path $liveProfile 'test-profile.txt'), 'live fixture profile', $utf8)
  $originalConfig = [IO.File]::ReadAllText($paths.Config)
  $originalEndpoint = $null
  $originalRealm = $null
  $originalRealmList = [IO.File]::ReadAllBytes($paths.RealmList)
  Save-ConnectionRecovery $paths $originalEndpoint $originalRealm $originalRealmList
  $protectedTry = @($ast.FindAll({ param($node)
      $node -is [Management.Automation.Language.TryStatementAst] -and $null -ne $node.Finally -and
      $node.Body.Extent.Text.Contains('Copy-StagingProfiles') -and $node.Finally.Extent.Text.Contains('Restore-ClientConnection')
    }, $true))
  Assert-Test ($protectedTry.Count -eq 1) 'Profile copying must sit inside exactly one connection recovery guard.'
  $script:FailProfileCopy = $true
  Assert-Throws { & ([scriptblock]::Create($protectedTry[0].Extent.Text)) } 'A profile-copy failure should be reported.'
  $script:FailProfileCopy = $false
  Assert-Test (-not (Test-Path -LiteralPath $paths.RecoveryFile)) 'A profile-copy failure must still clean up valid recovery data.'
  Assert-Test ([IO.File]::ReadAllText($paths.Config) -ceq $plain) 'A profile-copy failure must leave the original connection settings.'
  Copy-StagingProfiles $paths.Client
  $stageProfileFile = Join-Path $paths.Client 'WTF\Account\synthetic-account\COA G1 STAGING\test-profile.txt'
  Assert-Test ([IO.File]::ReadAllText($stageProfileFile) -ceq 'live fixture profile') 'A missing staging profile should be copied once.'
  [IO.File]::WriteAllText($stageProfileFile, 'existing staging profile', $utf8)
  Copy-StagingProfiles $paths.Client
  Assert-Test ([IO.File]::ReadAllText($stageProfileFile) -ceq 'existing staging profile') 'An existing staging profile must never be overwritten.'
  Assert-Test ([IO.File]::ReadAllText((Join-Path $liveProfile 'test-profile.txt')) -ceq 'live fixture profile') 'The live profile must remain unchanged.'

  Copy-StagingProfiles $paths.Client -Candidate
  $candidateProfileFile = Join-Path $paths.Client 'WTF\Account\synthetic-account\COA G1 CANDIDATE\test-profile.txt'
  Assert-Test ([IO.File]::ReadAllText($candidateProfileFile) -ceq 'existing staging profile') 'A new candidate profile must prefer the existing staging profile in the same client.'
  [IO.File]::WriteAllText($candidateProfileFile, 'existing candidate profile', $utf8)
  Copy-StagingProfiles $paths.Client -Candidate
  Assert-Test ([IO.File]::ReadAllText($candidateProfileFile) -ceq 'existing candidate profile') 'An existing candidate profile must never be overwritten.'
  Assert-Test ([IO.File]::ReadAllText($stageProfileFile) -ceq 'existing staging profile') 'Candidate profile copying must not change the baseline profile.'
  Assert-Test ([IO.File]::ReadAllText((Join-Path $liveProfile 'test-profile.txt')) -ceq 'live fixture profile') 'Candidate profile copying must not change the AzerothCore profile.'

  $paths = New-Fixture 'candidate-fallback' $plain
  $fallbackProfile = Join-Path $paths.Client 'WTF\Account\fallback-account\AzerothCore'
  New-Item -ItemType Directory -Path $fallbackProfile | Out-Null
  [IO.File]::WriteAllText((Join-Path $fallbackProfile 'fallback.txt'), 'fallback fixture', $utf8)
  Copy-StagingProfiles $paths.Client -Candidate
  Assert-Test ([IO.File]::ReadAllText((Join-Path $paths.Client 'WTF\Account\fallback-account\COA G1 CANDIDATE\fallback.txt')) -ceq 'fallback fixture') 'A candidate profile without a baseline profile must fall back to the same client AzerothCore profile.'
  Assert-Test (-not (Test-Path -LiteralPath (Join-Path $paths.Client 'WTF\Account\fallback-account\COA G1 STAGING'))) 'Candidate mode must not create or alter a baseline profile during fallback.'
  Assert-Test ([IO.File]::ReadAllText((Join-Path $fallbackProfile 'fallback.txt')) -ceq 'fallback fixture') 'The fallback source must remain unchanged.'
  $originalConfig = [IO.File]::ReadAllText($paths.Config)
  $originalRealmList = [IO.File]::ReadAllBytes($paths.RealmList)
  Save-ConnectionRecovery $paths $null $null $originalRealmList
  $candidateChanged = Set-ClientSetting $plain 'realmList' $candidateConnection.Endpoint
  $candidateChanged = Set-ClientSetting $candidateChanged 'realmName' $candidateConnection.Realm
  [IO.File]::WriteAllText($paths.Config, $candidateChanged, $utf8)
  [IO.File]::WriteAllText($paths.RealmList, ('set realmlist ' + $candidateConnection.Endpoint), $utf8)
  Restore-ClientConnection $paths
  Assert-Test ([IO.File]::ReadAllText($paths.Config) -ceq $plain) 'Candidate connection settings must restore through the unchanged recovery path.'
  Assert-Test ((Get-BytesHash ([IO.File]::ReadAllBytes($paths.RealmList))) -ceq (Get-BytesHash $originalRealmList)) 'Candidate recovery must restore exact realm-list bytes.'
  Assert-Test (-not (Test-Path -LiteralPath $paths.RecoveryFile)) 'Candidate successful recovery must remove its shared recovery marker.'

  $paths = New-Fixture 'candidate-profile-failure' $plain
  $candidateSource = Join-Path $paths.Client 'WTF\Account\candidate-failure-account\COA G1 STAGING'
  New-Item -ItemType Directory -Path $candidateSource | Out-Null
  [IO.File]::WriteAllText((Join-Path $candidateSource 'source.txt'), 'baseline fixture', $utf8)
  $originalConfig = [IO.File]::ReadAllText($paths.Config)
  Save-ConnectionRecovery $paths $null $null ([IO.File]::ReadAllBytes($paths.RealmList))
  $Candidate = $true
  $script:FailProfileCopy = $true
  Assert-Throws { & ([scriptblock]::Create($protectedTry[0].Extent.Text)) } 'A candidate profile-copy failure should be reported without launching.'
  $script:FailProfileCopy = $false
  $Candidate = $false
  Assert-Test (-not (Test-Path -LiteralPath $paths.RecoveryFile)) 'A candidate profile-copy failure must still restore and clean up recovery.'
  Assert-Test ([IO.File]::ReadAllText($paths.Config) -ceq $plain) 'A candidate profile-copy failure must leave the original connection unchanged.'
  Assert-Test ([IO.File]::ReadAllText((Join-Path $candidateSource 'source.txt')) -ceq 'baseline fixture') 'A failed candidate copy must leave the baseline source intact.'

  Write-Host "Staging launcher: $script:Checks checks passed. No real client files or game processes were used."
} finally {
  # Only delete the exact generated fixture directory inside the system temporary directory.
  $resolvedFixture = [IO.Path]::GetFullPath($fixtureRoot)
  if (-not $resolvedFixture.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
      [IO.Path]::GetFileName($resolvedFixture) -cne $fixtureName) { throw 'Unsafe test cleanup path.' }
  Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
}
