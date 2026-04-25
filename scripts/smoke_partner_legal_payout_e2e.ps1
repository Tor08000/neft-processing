$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_partner_legal_payout_e2e"
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

function Resolve-Url {
    param(
        [string]$Value,
        [string]$BaseUrl
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }
    if ($Value -match "^https?://") {
        return $Value
    }
    if ($Value.StartsWith("/")) {
        return $BaseUrl.TrimEnd("/") + $Value
    }
    return $BaseUrl.TrimEnd("/") + "/" + $Value.TrimStart("/")
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
        [ValidateSet("GET", "POST", "PUT")]
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
        if ([string]::IsNullOrWhiteSpace($content) -and $null -ne $_.ErrorDetails -and -not [string]::IsNullOrWhiteSpace($_.ErrorDetails.Message)) {
            $content = [string]$_.ErrorDetails.Message
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
    $response = Invoke-Api -Method POST -Url ($AuthUrl + "/login") -OutName $OutName -Body @{
        email = $Email
        password = $Password
        portal = $Portal
    }
    Write-Log ("Status: " + $response.StatusCode)
    Assert-Status -Step $Step -Actual $response.StatusCode -Expected @(200)
    Assert-True -Step $Step -Condition ($null -ne $response.Json -and -not [string]::IsNullOrWhiteSpace([string]$response.Json.access_token)) -Message "login response must include access_token"
    return [string]$response.Json.access_token
}

function Run-PartnerSeed {
    $seedScript = Join-Path $PSScriptRoot "seed_partner_money_e2e.cmd"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Log ("[0_seed] cmd /c scripts\seed_partner_money_e2e.cmd (attempt {0}/3)" -f $attempt)
        & cmd.exe /c $seedScript | ForEach-Object { Write-Log $_ }
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -lt 3) {
            Start-Sleep -Seconds 2
        }
    }
    throw "[0_seed] seed_partner_money_e2e.cmd failed"
}

function Extract-FinanceOrgId {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.entitlements_snapshot -and [string]$PortalMe.entitlements_snapshot.org_id -match "^\d+$") {
        return [string]$PortalMe.entitlements_snapshot.org_id
    }
    throw "partner portal/me did not expose numeric entitlements_snapshot.org_id"
}

function Extract-PartnerStorageId {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.partner -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.partner.partner_id)) {
        return [string]$PortalMe.partner.partner_id
    }
    if ($null -ne $PortalMe.org -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.org.id)) {
        return [string]$PortalMe.org.id
    }
    throw "partner portal/me did not expose partner storage id"
}

function Set-LegalStatus {
    param(
        [string]$CoreAdminUrl,
        [string]$AdminToken,
        [string]$PartnerId,
        [string]$Status,
        [string]$OutName
    )
    $response = Invoke-Api -Method POST -Url ($CoreAdminUrl + "/partners/" + $PartnerId + "/legal-profile/status") -OutName $OutName -Token $AdminToken -Body @{
        status = $Status
        comment = "smoke_partner_legal_payout"
    }
    Write-Log ("Status: " + $response.StatusCode)
    Assert-Status -Step ("legal_status_" + $Status) -Actual $response.StatusCode -Expected @(200)
    return $response
}

function Assert-PreviewReason {
    param(
        [string]$Step,
        [object]$Preview,
        [string]$Reason
    )
    $reasons = @(As-List $Preview.payout_block_reasons | ForEach-Object { [string]$_ })
    Assert-True -Step $Step -Condition ($reasons -contains $Reason) -Message ("preview must include " + $Reason)
}

function Assert-PreviewNoReason {
    param(
        [string]$Step,
        [object]$Preview,
        [string]$Reason
    )
    $reasons = @(As-List $Preview.payout_block_reasons | ForEach-Object { [string]$_ })
    Assert-True -Step $Step -Condition ($reasons -notcontains $Reason) -Message ("preview must not include " + $Reason)
}

Import-DotEnvDefaults

$baseUrl = Get-Config -Names @("BASE_URL", "GATEWAY_BASE_URL") -Default "http://localhost"
$authUrl = Resolve-Url -Value (Get-Config -Names @("AUTH_URL") -Default ($baseUrl + "/api/v1/auth")) -BaseUrl $baseUrl
$coreBase = Resolve-Url -Value (Get-Config -Names @("CORE_BASE") -Default ($baseUrl + "/api/core")) -BaseUrl $baseUrl
$corePortalUrl = Resolve-Url -Value (Get-Config -Names @("CORE_PORTAL_URL", "CORE_PORTAL") -Default ($coreBase + "/portal")) -BaseUrl $baseUrl
$corePartnerUrl = Resolve-Url -Value (Get-Config -Names @("CORE_PARTNER_URL", "CORE_PARTNER") -Default ($coreBase + "/partner")) -BaseUrl $baseUrl
$coreAdminUrl = Resolve-Url -Value (Get-Config -Names @("CORE_ADMIN_URL", "CORE_ADMIN") -Default ($coreBase + "/v1/admin")) -BaseUrl $baseUrl
$coreAdminFinanceUrl = Resolve-Url -Value (Get-Config -Names @("CORE_ADMIN_FINANCE_URL") -Default ($coreAdminUrl + "/finance")) -BaseUrl $baseUrl

[Environment]::SetEnvironmentVariable("BASE_URL", $baseUrl, "Process")
[Environment]::SetEnvironmentVariable("AUTH_URL", $authUrl, "Process")
[Environment]::SetEnvironmentVariable("CORE_BASE", $coreBase, "Process")
[Environment]::SetEnvironmentVariable("CORE_PORTAL", $corePortalUrl, "Process")
[Environment]::SetEnvironmentVariable("CORE_PARTNER", $corePartnerUrl, "Process")
[Environment]::SetEnvironmentVariable("CORE_ADMIN", $coreAdminUrl, "Process")
[Environment]::SetEnvironmentVariable("CORE_ADMIN_FINANCE_URL", $coreAdminFinanceUrl, "Process")

$adminEmail = Get-Config -Names @("ADMIN_EMAIL", "NEFT_BOOTSTRAP_ADMIN_EMAIL") -Default "admin@neft.local"
$adminPassword = Get-Config -Names @("ADMIN_PASSWORD", "NEFT_BOOTSTRAP_ADMIN_PASSWORD") -Default "Neft123!"
$partnerEmail = Get-Config -Names @("PARTNER_EMAIL", "NEFT_BOOTSTRAP_PARTNER_EMAIL") -Default "partner@neft.local"
$partnerPassword = Get-Config -Names @("PARTNER_PASSWORD", "NEFT_BOOTSTRAP_PARTNER_PASSWORD") -Default "Partner123!"

$adminToken = ""
$financeOrgId = ""
$partnerStorageId = ""
$exitCode = 0

try {
    Write-Log ("Starting {0}" -f $script:ScriptName)
    Write-Log ("BASE_URL={0}" -f $baseUrl)
    Write-Log ("CORE_PARTNER_URL={0}" -f $corePartnerUrl)
    Write-Log ("CORE_PORTAL_URL={0}" -f $corePortalUrl)
    Write-Log ("CORE_ADMIN_URL={0}" -f $coreAdminUrl)

    Run-PartnerSeed

    $step = "1_login"
    $adminToken = Get-Config -Names @("ADMIN_TOKEN") -Default ""
    if ([string]::IsNullOrWhiteSpace($adminToken)) {
        $adminToken = Login-OrThrow -Step $step -AuthUrl $authUrl -Email $adminEmail -Password $adminPassword -Portal "admin" -OutName "admin_login.json"
    }
    $partnerToken = Get-Config -Names @("PARTNER_TOKEN") -Default ""
    if ([string]::IsNullOrWhiteSpace($partnerToken)) {
        $partnerToken = Login-OrThrow -Step $step -AuthUrl $authUrl -Email $partnerEmail -Password $partnerPassword -Portal "partner" -OutName "partner_login.json"
    }

    $step = "2_partner_context"
    Write-Log ("[{0}] GET {1}/me" -f $step, $corePortalUrl)
    $portalMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "partner_portal_me.json" -Token $partnerToken
    Write-Log ("Status: " + $portalMe.StatusCode)
    Assert-Status -Step $step -Actual $portalMe.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($portalMe.Json.actor_type -eq "partner") -Message "portal/me must resolve partner actor"
    $financeOrgId = Extract-FinanceOrgId -PortalMe $portalMe.Json
    $partnerStorageId = Extract-PartnerStorageId -PortalMe $portalMe.Json
    Write-Log ("PARTNER_STORAGE_ID={0}" -f $partnerStorageId)
    Write-Log ("FINANCE_ORG_ID={0}" -f $financeOrgId)

    $step = "3_partner_legal_profile"
    Write-Log ("[{0}] PUT {1}/legal/profile" -f $step, $corePartnerUrl)
    $legalProfile = Invoke-Api -Method PUT -Url ($corePartnerUrl + "/legal/profile") -OutName "partner_legal_profile.json" -Token $partnerToken -Body @{
        legal_type = "LEGAL_ENTITY"
        country = "RU"
        tax_residency = "RU"
        tax_regime = "OSNO"
        vat_applicable = $true
        vat_rate = 20
    }
    Write-Log ("Status: " + $legalProfile.StatusCode)
    Assert-Status -Step $step -Actual $legalProfile.StatusCode -Expected @(200)

    Write-Log ("[{0}] PUT {1}/legal/details" -f $step, $corePartnerUrl)
    $legalDetails = Invoke-Api -Method PUT -Url ($corePartnerUrl + "/legal/details") -OutName "partner_legal_details.json" -Token $partnerToken -Body @{
        legal_name = "Smoke Partner LLC"
        inn = "7700000000"
        kpp = "770101001"
        ogrn = "1027700132195"
        bank_account = "40702810900000000001"
        bank_bic = "044525225"
        bank_name = "Demo Bank"
    }
    Write-Log ("Status: " + $legalDetails.StatusCode)
    Assert-Status -Step $step -Actual $legalDetails.StatusCode -Expected @(200)

    $step = "4_legal_blocks_payout"
    Write-Log ("[{0}] POST {1}/partners/{2}/legal-profile/status BLOCKED" -f $step, $coreAdminUrl, $financeOrgId)
    Set-LegalStatus -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -PartnerId $financeOrgId -Status "BLOCKED" -OutName "legal_status_blocked.json" | Out-Null

    Write-Log ("[{0}] POST {1}/payouts/preview" -f $step, $corePartnerUrl)
    $blockedPreview = Invoke-Api -Method POST -Url ($corePartnerUrl + "/payouts/preview") -OutName "payout_preview_blocked.json" -Token $partnerToken
    Write-Log ("Status: " + $blockedPreview.StatusCode)
    Assert-Status -Step $step -Actual $blockedPreview.StatusCode -Expected @(200)
    Assert-PreviewReason -Step $step -Preview $blockedPreview.Json -Reason "LEGAL_PENDING"

    Write-Log ("[{0}] POST {1}/payouts/request expect blocked" -f $step, $corePartnerUrl)
    $blockedRequest = Invoke-Api -Method POST -Url ($corePartnerUrl + "/payouts/request") -OutName "payout_request_blocked.json" -Token $partnerToken -Body @{
        amount = 1000
        currency = "RUB"
    }
    Write-Log ("Status: " + $blockedRequest.StatusCode)
    Assert-Status -Step $step -Actual $blockedRequest.StatusCode -Expected @(403, 409)
    Assert-True -Step $step -Condition ($blockedRequest.Content -match "LEGAL_PENDING|legal_status_not_verified|LEGAL_NOT_VERIFIED") -Message "blocked payout response must explain legal blocker"

    $step = "5_legal_verified_allows_payout"
    Write-Log ("[{0}] POST {1}/partners/{2}/legal-profile/status VERIFIED" -f $step, $coreAdminUrl, $financeOrgId)
    Set-LegalStatus -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -PartnerId $financeOrgId -Status "VERIFIED" -OutName "legal_status_verified_finance.json" | Out-Null
    if ($partnerStorageId -ne $financeOrgId) {
        Write-Log ("[{0}] POST {1}/partners/{2}/legal-profile/status VERIFIED" -f $step, $coreAdminUrl, $partnerStorageId)
        Set-LegalStatus -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -PartnerId $partnerStorageId -Status "VERIFIED" -OutName "legal_status_verified_storage.json" | Out-Null
    }

    Write-Log ("[{0}] POST {1}/payouts/preview" -f $step, $corePartnerUrl)
    $verifiedPreview = Invoke-Api -Method POST -Url ($corePartnerUrl + "/payouts/preview") -OutName "payout_preview_verified.json" -Token $partnerToken
    Write-Log ("Status: " + $verifiedPreview.StatusCode)
    Assert-Status -Step $step -Actual $verifiedPreview.StatusCode -Expected @(200)
    Assert-PreviewNoReason -Step $step -Preview $verifiedPreview.Json -Reason "LEGAL_PENDING"

    Write-Log ("[{0}] POST {1}/payouts/request" -f $step, $corePartnerUrl)
    $payoutRequest = Invoke-Api -Method POST -Url ($corePartnerUrl + "/payouts/request") -OutName "payout_request_allowed.json" -Token $partnerToken -Body @{
        amount = 1000
        currency = "RUB"
    }
    Write-Log ("Status: " + $payoutRequest.StatusCode)
    Assert-Status -Step $step -Actual $payoutRequest.StatusCode -Expected @(200, 201)
    $payoutId = [string]$payoutRequest.Json.payout_request_id
    if ([string]::IsNullOrWhiteSpace($payoutId)) {
        $payoutId = [string]$payoutRequest.Json.id
    }
    $correlationId = [string]$payoutRequest.Json.correlation_id
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace($payoutId)) -Message "payout response must include id"
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace($correlationId)) -Message "payout response must include correlation_id"

    $step = "6_admin_approve_and_pack"
    Write-Log ("[{0}] POST {1}/payouts/{2}/approve" -f $step, $coreAdminFinanceUrl, $payoutId)
    $approve = Invoke-Api -Method POST -Url ($coreAdminFinanceUrl + "/payouts/" + $payoutId + "/approve") -OutName "payout_approve.json" -Token $adminToken -Body @{
        reason = "Smoke approval"
        correlation_id = $correlationId
    }
    Write-Log ("Status: " + $approve.StatusCode)
    Assert-Status -Step $step -Actual $approve.StatusCode -Expected @(200)

    Write-Log ("[{0}] POST {1}/partners/{2}/legal-pack" -f $step, $coreAdminUrl, $financeOrgId)
    $pack = Invoke-Api -Method POST -Url ($coreAdminUrl + "/partners/" + $financeOrgId + "/legal-pack") -OutName "legal_pack.json" -Token $adminToken -Body @{
        format = "ZIP"
    }
    Write-Log ("Status: " + $pack.StatusCode)
    Assert-Status -Step $step -Actual $pack.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace([string]$pack.Json.id)) -Message "legal pack response must include id"

    Write-Log "E2E_PARTNER_LEGAL_PAYOUT: PASS"
} catch {
    $exitCode = 1
    Write-Log ("E2E_PARTNER_LEGAL_PAYOUT: FAIL - " + $_.Exception.Message)
} finally {
    if (-not [string]::IsNullOrWhiteSpace($adminToken) -and -not [string]::IsNullOrWhiteSpace($financeOrgId)) {
        try {
            Write-Log ("[cleanup] ensure finance legal status VERIFIED for {0}" -f $financeOrgId)
            Set-LegalStatus -CoreAdminUrl $coreAdminUrl -AdminToken $adminToken -PartnerId $financeOrgId -Status "VERIFIED" -OutName "cleanup_legal_status_verified_finance.json" | Out-Null
        } catch {
            $exitCode = 1
            Write-Log ("[cleanup] failed - " + $_.Exception.Message)
        }
    }
}

exit $exitCode
