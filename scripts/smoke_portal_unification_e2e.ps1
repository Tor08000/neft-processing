$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_portal_unification_e2e"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:RunTs = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogDir = Join-Path $script:RepoRoot "logs"
$script:TempDir = Join-Path $env:TEMP ($script:ScriptName + "_" + $script:RunTs)
$script:LogFile = Join-Path $script:LogDir ($script:ScriptName + "_" + $script:RunTs + ".log")

New-Item -ItemType Directory -Force -Path $script:LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $script:TempDir | Out-Null

function Write-Log {
    param([string]$Message)
    Write-Host $Message
    Add-Content -Path $script:LogFile -Value $Message
}

function Import-DotEnvDefaults {
    $envPath = Join-Path $script:RepoRoot ".env"
    if (-not (Test-Path $envPath)) {
        return
    }
    foreach ($line in Get-Content -Path $envPath) {
        if ($line -match "^\s*#" -or $line -notmatch "^\s*([^=]+?)\s*=\s*(.*)\s*$") {
            continue
        }
        $key = $matches[1].Trim()
        $value = $matches[2].Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($key, "Process")) {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Get-Config {
    param(
        [string[]]$Names,
        [string]$Default = ""
    )
    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }
    return $Default
}

function Save-Response {
    param(
        [string]$Name,
        [string]$Content
    )
    $path = Join-Path $script:TempDir $Name
    if ($null -eq $Content) {
        $Content = ""
    }
    [System.IO.File]::WriteAllText($path, $Content, [System.Text.UTF8Encoding]::new($false))
    Add-Content -Path $script:LogFile -Value ("---- response from " + $path + " ----")
    Add-Content -Path $script:LogFile -Value $Content
    return $path
}

function Invoke-Api {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Url,
        [string]$OutName,
        [string]$Token = "",
        [object]$Body = $null
    )

    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = if ($Token.StartsWith("Bearer ")) { $Token } else { "Bearer $Token" }
    }

    $bodyJson = $null
    if ($null -ne $Body) {
        $bodyJson = $Body | ConvertTo-Json -Compress -Depth 20
    }

    try {
        if ($null -ne $bodyJson) {
            $response = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers -ContentType "application/json" -Body $bodyJson -UseBasicParsing
        } else {
            $response = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers -UseBasicParsing
        }
        $statusCode = [int]$response.StatusCode
        $content = [string]$response.Content
    } catch {
        $webResponse = $_.Exception.Response
        if ($null -eq $webResponse) {
            throw
        }
        $statusCode = [int]$webResponse.StatusCode
        $stream = $webResponse.GetResponseStream()
        if ($null -eq $stream) {
            $content = ""
        } else {
            $reader = New-Object System.IO.StreamReader($stream)
            $content = $reader.ReadToEnd()
            $reader.Dispose()
        }
    }

    $path = Save-Response -Name $OutName -Content $content
    $json = $null
    if (-not [string]::IsNullOrWhiteSpace($content)) {
        try {
            $json = $content | ConvertFrom-Json
        } catch {
            $json = $null
        }
    }

    [pscustomobject]@{
        StatusCode = $statusCode
        Content    = $content
        Json       = $json
        Path       = $path
    }
}

function Assert-Status {
    param(
        [string]$Step,
        [int]$Actual,
        [int[]]$Expected
    )
    if ($Expected -notcontains $Actual) {
        throw ("[{0}] expected HTTP {1}, got {2}" -f $Step, ($Expected -join ","), $Actual)
    }
}

function Assert-True {
    param(
        [string]$Step,
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw ("[{0}] {1}" -f $Step, $Message)
    }
}

function As-List {
    param([object]$Value)
    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [System.Array]) {
        return @($Value)
    }
    return @($Value)
}

function Normalize-UpperList {
    param([object]$Value)
    @(As-List $Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.ToUpperInvariant() })
}

function Try-Login {
    param(
        [string]$AuthUrl,
        [string]$Email,
        [string]$Password,
        [string]$Portal,
        [string]$OutName
    )
    $response = Invoke-Api -Method POST -Url ($AuthUrl + "/login") -OutName $OutName -Body @{
        email = $Email
        password = $Password
        portal = $Portal
    }
    if ($response.StatusCode -ne 200 -or $null -eq $response.Json -or [string]::IsNullOrWhiteSpace([string]$response.Json.access_token)) {
        return $null
    }
    return [string]$response.Json.access_token
}

function Login-OrThrow {
    param(
        [string]$Step,
        [string]$AuthUrl,
        [string]$Email,
        [string]$Password,
        [string]$Portal,
        [string]$OutName
    )
    Write-Log ("[{0}] POST {1}/login ({2})" -f $Step, $AuthUrl, $Portal)
    $token = Try-Login -AuthUrl $AuthUrl -Email $Email -Password $Password -Portal $Portal -OutName $OutName
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw ("[{0}] login failed for {1} portal user {2}" -f $Step, $Portal, $Email)
    }
    return $token
}

function Ensure-Partner-Seed {
    param([string]$AuthUrl, [string]$PartnerEmail, [string]$PartnerPassword)
    $probe = Try-Login -AuthUrl $AuthUrl -Email $PartnerEmail -Password $PartnerPassword -Portal "partner" -OutName "partner_login_probe.json"
    if (-not [string]::IsNullOrWhiteSpace($probe)) {
        return $probe
    }

    Write-Log "[seed_partner] partner login not ready; running seed_partner_money_e2e.cmd"
    $seedScript = Join-Path $PSScriptRoot "seed_partner_money_e2e.cmd"
    & cmd.exe /c $seedScript | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "[seed_partner] seed_partner_money_e2e.cmd failed"
    }

    $token = Try-Login -AuthUrl $AuthUrl -Email $PartnerEmail -Password $PartnerPassword -Portal "partner" -OutName "partner_login_after_seed.json"
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "[seed_partner] partner login still failed after seed"
    }
    return $token
}

function Extract-NumericOrgId {
    param([object]$PortalMe)
    $candidates = @()
    if ($null -ne $PortalMe.entitlements_snapshot) {
        $candidates += [string]$PortalMe.entitlements_snapshot.org_id
    }
    if ($null -ne $PortalMe.billing) {
        $candidates += [string]$PortalMe.billing.org_id
    }
    foreach ($candidate in $candidates) {
        if ($candidate -match "^\d+$") {
            return [int]$candidate
        }
    }
    return $null
}

function Recompute-Entitlements {
    param([string]$CoreAdminUrl, [string]$AdminToken, [int]$OrgId, [string]$OutName)
    $response = Invoke-Api -Method POST -Url ($CoreAdminUrl + "/commercial/orgs/" + $OrgId + "/entitlements/recompute") -OutName $OutName -Token $AdminToken -Body @{ reason = "smoke_portal_unification" }
    Assert-Status -Step "recompute_entitlements" -Actual $response.StatusCode -Expected @(200)
}

Import-DotEnvDefaults

$baseUrl = Get-Config -Names @("BASE_URL", "GATEWAY_BASE_URL") -Default "http://localhost"
$authUrl = Get-Config -Names @("AUTH_URL") -Default ($baseUrl + "/api/v1/auth")
$coreBase = Get-Config -Names @("CORE_BASE") -Default ($baseUrl + "/api/core")
$corePortalUrl = Get-Config -Names @("CORE_PORTAL_URL", "CORE_PORTAL") -Default ($coreBase + "/portal")
$coreClientUrl = Get-Config -Names @("CORE_CLIENT_URL", "CORE_CLIENT") -Default ($coreBase + "/client")
$corePartnerUrl = Get-Config -Names @("CORE_PARTNER_URL", "CORE_PARTNER") -Default ($coreBase + "/partner")
$coreAdminUrl = Get-Config -Names @("CORE_ADMIN_URL", "CORE_ADMIN") -Default ($coreBase + "/v1/admin")

$adminEmail = Get-Config -Names @("ADMIN_EMAIL", "NEFT_BOOTSTRAP_ADMIN_EMAIL") -Default "admin@neft.local"
$adminPassword = Get-Config -Names @("ADMIN_PASSWORD", "NEFT_BOOTSTRAP_ADMIN_PASSWORD") -Default "Neft123!"
$clientEmail = Get-Config -Names @("CLIENT_EMAIL", "NEFT_BOOTSTRAP_CLIENT_EMAIL") -Default "client@neft.local"
$clientPassword = Get-Config -Names @("CLIENT_PASSWORD", "NEFT_BOOTSTRAP_CLIENT_PASSWORD") -Default "Client123!"
$partnerEmail = Get-Config -Names @("PARTNER_EMAIL", "NEFT_BOOTSTRAP_PARTNER_EMAIL") -Default "partner@neft.local"
$partnerPassword = Get-Config -Names @("PARTNER_PASSWORD", "NEFT_BOOTSTRAP_PARTNER_PASSWORD") -Default "Partner123!"

$addedPartnerRole = $false
$orgId = $null
$exitCode = 0

try {
    Write-Log ("Starting {0}" -f $script:ScriptName)
    Write-Log ("BASE_URL={0}" -f $baseUrl)
    Write-Log ("CORE_PORTAL_URL={0}" -f $corePortalUrl)
    Write-Log ("CORE_CLIENT_URL={0}" -f $coreClientUrl)
    Write-Log ("CORE_PARTNER_URL={0}" -f $corePartnerUrl)
    Write-Log ("CORE_ADMIN_URL={0}" -f $coreAdminUrl)

    $step = "0_health"
    Write-Log ("[{0}] GET {1}/health" -f $step, $coreBase)
    $health = Invoke-Api -Method GET -Url ($coreBase + "/health") -OutName "core_health.json"
    Write-Log ("Status: " + $health.StatusCode)
    Assert-Status -Step $step -Actual $health.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($health.Json.status -eq "ok") -Message "core health must be ok"

    $step = "1_login_tokens"
    $adminToken = Get-Config -Names @("ADMIN_TOKEN") -Default ""
    if ([string]::IsNullOrWhiteSpace($adminToken)) {
        $adminToken = Login-OrThrow -Step $step -AuthUrl $authUrl -Email $adminEmail -Password $adminPassword -Portal "admin" -OutName "admin_login.json"
    }
    $clientToken = Get-Config -Names @("CLIENT_TOKEN") -Default ""
    if ([string]::IsNullOrWhiteSpace($clientToken)) {
        $clientToken = Login-OrThrow -Step $step -AuthUrl $authUrl -Email $clientEmail -Password $clientPassword -Portal "client" -OutName "client_login.json"
    }
    $partnerToken = Get-Config -Names @("PARTNER_TOKEN") -Default ""
    if ([string]::IsNullOrWhiteSpace($partnerToken)) {
        $partnerToken = Ensure-Partner-Seed -AuthUrl $authUrl -PartnerEmail $partnerEmail -PartnerPassword $partnerPassword
    }

    $step = "2_verify_token_families"
    Write-Log ("[{0}] GET {1}/auth/verify with client token" -f $step, $coreClientUrl)
    $clientVerify = Invoke-Api -Method GET -Url ($coreClientUrl + "/auth/verify") -OutName "client_verify.txt" -Token $clientToken
    Write-Log ("Status: " + $clientVerify.StatusCode)
    Assert-Status -Step $step -Actual $clientVerify.StatusCode -Expected @(204)

    Write-Log ("[{0}] GET {1}/auth/verify with partner token" -f $step, $corePartnerUrl)
    $partnerVerify = Invoke-Api -Method GET -Url ($corePartnerUrl + "/auth/verify") -OutName "partner_verify.txt" -Token $partnerToken
    Write-Log ("Status: " + $partnerVerify.StatusCode)
    Assert-Status -Step $step -Actual $partnerVerify.StatusCode -Expected @(204)

    Write-Log ("[{0}] GET {1}/auth/verify with client token must be rejected" -f $step, $corePartnerUrl)
    $clientAsPartner = Invoke-Api -Method GET -Url ($corePartnerUrl + "/auth/verify") -OutName "client_as_partner_verify.json" -Token $clientToken
    Write-Log ("Status: " + $clientAsPartner.StatusCode)
    Assert-Status -Step $step -Actual $clientAsPartner.StatusCode -Expected @(401, 403)

    Write-Log ("[{0}] GET {1}/auth/verify with partner token must be rejected" -f $step, $coreClientUrl)
    $partnerAsClient = Invoke-Api -Method GET -Url ($coreClientUrl + "/auth/verify") -OutName "partner_as_client_verify.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerAsClient.StatusCode)
    Assert-Status -Step $step -Actual $partnerAsClient.StatusCode -Expected @(401, 403)

    $step = "3_client_actor_with_mixed_org_roles"
    Write-Log ("[{0}] GET {1}/me with client token" -f $step, $corePortalUrl)
    $clientMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "client_portal_me_before.json" -Token $clientToken
    Write-Log ("Status: " + $clientMe.StatusCode)
    Assert-Status -Step $step -Actual $clientMe.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($clientMe.Json.actor_type -eq "client") -Message "client token must resolve actor_type=client"
    Assert-True -Step $step -Condition ($null -eq $clientMe.Json.partner) -Message "client portal/me must not expose partner actor payload"

    $orgId = Extract-NumericOrgId -PortalMe $clientMe.Json
    Assert-True -Step $step -Condition ($null -ne $orgId) -Message "client portal/me must expose numeric entitlements org_id for commercial role checks"
    $clientRolesBefore = Normalize-UpperList $clientMe.Json.org_roles
    if ($clientRolesBefore -notcontains "PARTNER") {
        Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/roles/add PARTNER" -f $step, $coreAdminUrl, $orgId)
        $addPartnerRole = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/roles/add") -OutName "add_partner_role.json" -Token $adminToken -Body @{
            role = "PARTNER"
            reason = "smoke_portal_unification_mixed_roles"
        }
        Write-Log ("Status: " + $addPartnerRole.StatusCode)
        Assert-Status -Step $step -Actual $addPartnerRole.StatusCode -Expected @(200)
        $addedPartnerRole = $true
        Recompute-Entitlements -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -OrgId $orgId -OutName "client_recompute_after_role_add.json"
    }

    $clientMeMixed = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "client_portal_me_mixed.json" -Token $clientToken
    Write-Log ("Status: " + $clientMeMixed.StatusCode)
    Assert-Status -Step $step -Actual $clientMeMixed.StatusCode -Expected @(200)
    $clientMemberships = Normalize-UpperList $clientMeMixed.Json.memberships
    $clientOrgRoles = Normalize-UpperList $clientMeMixed.Json.org_roles
    Assert-True -Step $step -Condition ($clientMeMixed.Json.actor_type -eq "client") -Message "mixed org roles must not flip client token to partner actor"
    Assert-True -Step $step -Condition ($clientMemberships -contains "CLIENT") -Message "client memberships must include CLIENT"
    Assert-True -Step $step -Condition ($clientOrgRoles -contains "PARTNER") -Message "mixed role fixture must include PARTNER org role"
    Assert-True -Step $step -Condition ($null -eq $clientMeMixed.Json.partner) -Message "client actor must keep partner payload null even with PARTNER org role"

    $step = "4_partner_actor_projection"
    Write-Log ("[{0}] GET {1}/me with partner token" -f $step, $corePortalUrl)
    $partnerMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "partner_portal_me.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerMe.StatusCode)
    Assert-Status -Step $step -Actual $partnerMe.StatusCode -Expected @(200)
    $partnerRoles = Normalize-UpperList $partnerMe.Json.user_roles
    Assert-True -Step $step -Condition ($partnerMe.Json.actor_type -eq "partner") -Message "partner token must resolve actor_type=partner"
    Assert-True -Step $step -Condition ($null -ne $partnerMe.Json.partner) -Message "partner portal/me must expose partner payload"
    Assert-True -Step $step -Condition ($partnerRoles -contains "PARTNER_OWNER" -or $partnerRoles -contains "PARTNER_ACCOUNTANT") -Message "partner user role must be explicit"
    Assert-True -Step $step -Condition ($partnerMe.Json.access_state -ne "TECH_ERROR") -Message "partner portal/me must not degrade to TECH_ERROR"

    Write-Log ("[{0}] GET {1}/finance/dashboard with partner token" -f $step, $corePartnerUrl)
    $partnerFinance = Invoke-Api -Method GET -Url ($corePartnerUrl + "/finance/dashboard") -OutName "partner_finance_dashboard.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerFinance.StatusCode)
    Assert-Status -Step $step -Actual $partnerFinance.StatusCode -Expected @(200)

    Write-Log ("[{0}] GET {1}/me removed alias must stay absent" -f $step, $corePartnerUrl)
    $removedPartnerMe = Invoke-Api -Method GET -Url ($corePartnerUrl + "/me") -OutName "partner_me_removed_alias.json" -Token $partnerToken
    Write-Log ("Status: " + $removedPartnerMe.StatusCode)
    Assert-Status -Step $step -Actual $removedPartnerMe.StatusCode -Expected @(404)

    Write-Log "E2E_PORTAL_UNIFICATION: PASS"
} catch {
    $exitCode = 1
    Write-Log ("E2E_PORTAL_UNIFICATION: FAIL - " + $_.Exception.Message)
} finally {
    if ($addedPartnerRole -and $null -ne $orgId) {
        try {
            Write-Log ("[cleanup] POST {0}/commercial/orgs/{1}/roles/remove PARTNER" -f $coreAdminUrl, $orgId)
            $removePartnerRole = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/roles/remove") -OutName "remove_partner_role.json" -Token $adminToken -Body @{
                role = "PARTNER"
                reason = "smoke_portal_unification_cleanup"
            }
            Write-Log ("Status: " + $removePartnerRole.StatusCode)
            Assert-Status -Step "cleanup" -Actual $removePartnerRole.StatusCode -Expected @(200)
            Recompute-Entitlements -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -OrgId $orgId -OutName "client_recompute_cleanup.json"
        } catch {
            $exitCode = 1
            Write-Log ("[cleanup] failed - " + $_.Exception.Message)
        }
    }
}

exit $exitCode
