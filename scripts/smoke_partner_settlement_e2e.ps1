$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_partner_settlement_e2e"
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
    Write-Log "[0_seed] cmd /c scripts\seed_partner_money_e2e.cmd"
    & cmd.exe /c $seedScript | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "[0_seed] seed_partner_money_e2e.cmd failed"
    }
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

function Find-PartnerPayout {
    param(
        [object]$Payouts,
        [string[]]$PartnerIds
    )
    foreach ($item in As-List $Payouts.items) {
        $partnerOrg = [string]$item.partner_org
        if ($PartnerIds -contains $partnerOrg) {
            return $item
        }
    }
    return $null
}

Import-DotEnvDefaults

$baseUrl = Get-Config -Names @("BASE_URL", "GATEWAY_BASE_URL") -Default "http://localhost"
$authUrl = Get-Config -Names @("AUTH_URL") -Default ($baseUrl + "/api/v1/auth")
$coreBase = Get-Config -Names @("CORE_BASE") -Default ($baseUrl + "/api/core")
$corePortalUrl = Get-Config -Names @("CORE_PORTAL_URL", "CORE_PORTAL") -Default ($coreBase + "/portal")
$corePartnerUrl = Get-Config -Names @("CORE_PARTNER_URL", "CORE_PARTNER") -Default ($coreBase + "/partner")
$coreAdminUrl = Get-Config -Names @("CORE_ADMIN_URL", "CORE_ADMIN") -Default ($coreBase + "/v1/admin")
$coreAdminFinanceUrl = Get-Config -Names @("CORE_ADMIN_FINANCE_URL") -Default ($coreAdminUrl + "/finance")
$coreAdminBridgeUrl = Get-Config -Names @("CORE_ADMIN_BRIDGE_URL") -Default ($coreBase + "/admin")

$adminEmail = Get-Config -Names @("ADMIN_EMAIL", "NEFT_BOOTSTRAP_ADMIN_EMAIL") -Default "admin@neft.local"
$adminPassword = Get-Config -Names @("ADMIN_PASSWORD", "NEFT_BOOTSTRAP_ADMIN_PASSWORD") -Default "Neft123!"
$partnerEmail = Get-Config -Names @("PARTNER_EMAIL", "NEFT_BOOTSTRAP_PARTNER_EMAIL") -Default "partner@neft.local"
$partnerPassword = Get-Config -Names @("PARTNER_PASSWORD", "NEFT_BOOTSTRAP_PARTNER_PASSWORD") -Default "Partner123!"

$exitCode = 0

try {
    Write-Log ("Starting {0}" -f $script:ScriptName)
    Write-Log ("BASE_URL={0}" -f $baseUrl)
    Write-Log ("CORE_PARTNER_URL={0}" -f $corePartnerUrl)
    Write-Log ("CORE_ADMIN_FINANCE_URL={0}" -f $coreAdminFinanceUrl)

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
    Write-Log ("[{0}] GET {1}/auth/verify" -f $step, $corePartnerUrl)
    $verify = Invoke-Api -Method GET -Url ($corePartnerUrl + "/auth/verify") -OutName "partner_verify.txt" -Token $partnerToken
    Write-Log ("Status: " + $verify.StatusCode)
    Assert-Status -Step $step -Actual $verify.StatusCode -Expected @(204)

    Write-Log ("[{0}] GET {1}/me" -f $step, $corePortalUrl)
    $portalMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "partner_portal_me.json" -Token $partnerToken
    Write-Log ("Status: " + $portalMe.StatusCode)
    Assert-Status -Step $step -Actual $portalMe.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($portalMe.Json.actor_type -eq "partner") -Message "portal/me must resolve partner actor"
    $financeOrgId = Extract-FinanceOrgId -PortalMe $portalMe.Json
    $partnerStorageId = Extract-PartnerStorageId -PortalMe $portalMe.Json
    Write-Log ("FINANCE_ORG_ID={0}" -f $financeOrgId)
    Write-Log ("PARTNER_STORAGE_ID={0}" -f $partnerStorageId)

    $step = "3_partner_finance_surfaces"
    Write-Log ("[{0}] GET {1}/finance/dashboard" -f $step, $corePartnerUrl)
    $dashboard = Invoke-Api -Method GET -Url ($corePartnerUrl + "/finance/dashboard") -OutName "partner_dashboard.json" -Token $partnerToken
    Write-Log ("Status: " + $dashboard.StatusCode)
    Assert-Status -Step $step -Actual $dashboard.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $dashboard.Json.balance -and $dashboard.Json.currency -eq "RUB") -Message "dashboard must expose RUB balance"

    Write-Log ("[{0}] GET {1}/balance" -f $step, $corePartnerUrl)
    $balance = Invoke-Api -Method GET -Url ($corePartnerUrl + "/balance") -OutName "partner_balance.json" -Token $partnerToken
    Write-Log ("Status: " + $balance.StatusCode)
    Assert-Status -Step $step -Actual $balance.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($balance.Json.partner_org_id -eq $financeOrgId -and $null -ne $balance.Json.balance_available) -Message "balance must belong to finance org"

    Write-Log ("[{0}] GET {1}/ledger?limit=5" -f $step, $corePartnerUrl)
    $ledger = Invoke-Api -Method GET -Url ($corePartnerUrl + "/ledger?limit=5") -OutName "partner_ledger.json" -Token $partnerToken
    Write-Log ("Status: " + $ledger.StatusCode)
    Assert-Status -Step $step -Actual $ledger.StatusCode -Expected @(200)
    $ledgerItems = @(As-List $ledger.Json.items)
    Assert-True -Step $step -Condition ($ledgerItems.Count -gt 0 -and $null -ne $ledger.Json.totals) -Message "ledger must expose entries and totals"

    $entryId = [string]$ledgerItems[0].id
    Write-Log ("[{0}] GET {1}/ledger/{2}/explain" -f $step, $corePartnerUrl, $entryId)
    $ledgerExplain = Invoke-Api -Method GET -Url ($corePartnerUrl + "/ledger/" + $entryId + "/explain") -OutName "ledger_explain.json" -Token $partnerToken
    Write-Log ("Status: " + $ledgerExplain.StatusCode)
    Assert-Status -Step $step -Actual $ledgerExplain.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($ledgerExplain.Json.entry_id -eq $entryId -and -not [string]::IsNullOrWhiteSpace([string]$ledgerExplain.Json.operation)) -Message "ledger explain must be tied to entry"

    $step = "4_payout_preview_and_history_routes"
    Write-Log ("[{0}] GET {1}/payouts/preview" -f $step, $corePartnerUrl)
    $previewGet = Invoke-Api -Method GET -Url ($corePartnerUrl + "/payouts/preview") -OutName "payout_preview_get.json" -Token $partnerToken
    Write-Log ("Status: " + $previewGet.StatusCode)
    Assert-Status -Step $step -Actual $previewGet.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($previewGet.Json.partner_org_id -eq $financeOrgId -and $null -ne $previewGet.Json.available_to_withdraw) -Message "GET preview must not be shadowed by payout id route"

    Write-Log ("[{0}] POST {1}/payouts/preview" -f $step, $corePartnerUrl)
    $previewPost = Invoke-Api -Method POST -Url ($corePartnerUrl + "/payouts/preview") -OutName "payout_preview_post.json" -Token $partnerToken
    Write-Log ("Status: " + $previewPost.StatusCode)
    Assert-Status -Step $step -Actual $previewPost.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($previewPost.Json.partner_org_id -eq $financeOrgId) -Message "POST preview must resolve partner org"

    Write-Log ("[{0}] GET {1}/payouts/history" -f $step, $corePartnerUrl)
    $history = Invoke-Api -Method GET -Url ($corePartnerUrl + "/payouts/history") -OutName "payout_history.json" -Token $partnerToken
    Write-Log ("Status: " + $history.StatusCode)
    Assert-Status -Step $step -Actual $history.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $history.Json.requests) -Message "history must not be shadowed by payout id route"

    Write-Log ("[{0}] GET {1}/payouts" -f $step, $corePartnerUrl)
    $partnerPayouts = Invoke-Api -Method GET -Url ($corePartnerUrl + "/payouts") -OutName "partner_payouts.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerPayouts.StatusCode)
    Assert-Status -Step $step -Actual $partnerPayouts.StatusCode -Expected @(200)

    $step = "5_partner_documents"
    foreach ($path in @("invoices", "acts", "docs")) {
        Write-Log ("[{0}] GET {1}/{2}" -f $step, $corePartnerUrl, $path)
        $response = Invoke-Api -Method GET -Url ($corePartnerUrl + "/" + $path) -OutName ("partner_" + $path + ".json") -Token $partnerToken
        Write-Log ("Status: " + $response.StatusCode)
        Assert-Status -Step $step -Actual $response.StatusCode -Expected @(200)
        Assert-True -Step $step -Condition ($null -ne $response.Json.items) -Message ($path + " response must include items")
    }

    $step = "6_admin_settlement_snapshot"
    Write-Log ("[{0}] GET {1}/partner/{2}/settlement" -f $step, $coreAdminBridgeUrl, $partnerStorageId)
    $settlementSnapshot = Invoke-Api -Method GET -Url ($coreAdminBridgeUrl + "/partner/" + $partnerStorageId + "/settlement?currency=RUB") -OutName "admin_settlement_snapshot.json" -Token $adminToken
    Write-Log ("Status: " + $settlementSnapshot.StatusCode)
    Assert-Status -Step $step -Actual $settlementSnapshot.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace([string]$settlementSnapshot.Json.settlement_id) -and $settlementSnapshot.Json.currency -eq "RUB") -Message "admin settlement snapshot must be present"

    Write-Log ("[{0}] GET {1}/payouts?limit=20" -f $step, $coreAdminFinanceUrl)
    $adminPayouts = Invoke-Api -Method GET -Url ($coreAdminFinanceUrl + "/payouts?limit=20") -OutName "admin_payouts.json" -Token $adminToken
    Write-Log ("Status: " + $adminPayouts.StatusCode)
    Assert-Status -Step $step -Actual $adminPayouts.StatusCode -Expected @(200)
    $matchingPayout = Find-PartnerPayout -Payouts $adminPayouts.Json -PartnerIds @($financeOrgId, $partnerStorageId)
    if ($null -ne $matchingPayout) {
        $payoutId = [string]$matchingPayout.payout_id
        Write-Log ("[{0}] GET {1}/payouts/{2}" -f $step, $coreAdminFinanceUrl, $payoutId)
        $payoutDetail = Invoke-Api -Method GET -Url ($coreAdminFinanceUrl + "/payouts/" + $payoutId) -OutName "admin_payout_detail.json" -Token $adminToken
        Write-Log ("Status: " + $payoutDetail.StatusCode)
        Assert-Status -Step $step -Actual $payoutDetail.StatusCode -Expected @(200)
        Assert-True -Step $step -Condition ($null -ne $payoutDetail.Json.settlement_snapshot -and -not [string]::IsNullOrWhiteSpace([string]$payoutDetail.Json.settlement_snapshot.settlement_id)) -Message "payout detail must include settlement snapshot"
    } else {
        Write-Log ("[{0}] no payout exists for partner; settlement snapshot verified without payout mutation" -f $step)
    }

    $step = "7_partner_contracts_settlements_reads"
    Write-Log ("[{0}] GET {1}/contracts must be mounted read-only" -f $step, $corePartnerUrl)
    $coreContractsAlias = Invoke-Api -Method GET -Url ($corePartnerUrl + "/contracts") -OutName "core_partner_contracts_read.json" -Token $partnerToken
    Write-Log ("Status: " + $coreContractsAlias.StatusCode)
    Assert-Status -Step $step -Actual $coreContractsAlias.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $coreContractsAlias.Json.items) -Message "core partner contracts must include items list"

    Write-Log ("[{0}] GET {1}/api/partner/contracts must be mounted read-only" -f $step, $baseUrl)
    $legacyContractsAlias = Invoke-Api -Method GET -Url ($baseUrl + "/api/partner/contracts") -OutName "legacy_partner_contracts_read.json" -Token $partnerToken
    Write-Log ("Status: " + $legacyContractsAlias.StatusCode)
    Assert-Status -Step $step -Actual $legacyContractsAlias.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $legacyContractsAlias.Json.items) -Message "legacy partner contracts must include items list"

    Write-Log ("[{0}] GET {1}/settlements must be mounted read-only" -f $step, $corePartnerUrl)
    $coreSettlementAlias = Invoke-Api -Method GET -Url ($corePartnerUrl + "/settlements") -OutName "core_partner_settlements_read.json" -Token $partnerToken
    Write-Log ("Status: " + $coreSettlementAlias.StatusCode)
    Assert-Status -Step $step -Actual $coreSettlementAlias.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $coreSettlementAlias.Json.items) -Message "core partner settlements must include items list"

    Write-Log ("[{0}] GET {1}/api/partner/settlements must be mounted read-only" -f $step, $baseUrl)
    $legacySettlementAlias = Invoke-Api -Method GET -Url ($baseUrl + "/api/partner/settlements") -OutName "legacy_partner_settlements_read.json" -Token $partnerToken
    Write-Log ("Status: " + $legacySettlementAlias.StatusCode)
    Assert-Status -Step $step -Actual $legacySettlementAlias.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($null -ne $legacySettlementAlias.Json.items) -Message "legacy partner settlements must include items list"

    Write-Log ("[{0}] POST settlement confirm must remain absent" -f $step)
    $confirmTail = Invoke-Api -Method POST -Url ($baseUrl + "/api/partner/settlements/" + [guid]::NewGuid().ToString() + "/confirm") -OutName "legacy_partner_settlement_confirm_tail.json" -Token $partnerToken
    Write-Log ("Status: " + $confirmTail.StatusCode)
    Assert-Status -Step $step -Actual $confirmTail.StatusCode -Expected @(404)

    $evidencePath = Join-Path $script:RepoRoot "docs\diag\partner-finance-mounted-routes-live-smoke-20260425.json"
    New-Item -ItemType Directory -Force -Path (Split-Path $evidencePath -Parent) | Out-Null
    $evidence = [ordered]@{
        captured_at = (Get-Date).ToUniversalTime().ToString("o")
        surface = "partner_finance_contracts_settlements_read"
        status = "VERIFIED_RUNTIME"
        command = "cmd /c scripts\smoke_partner_settlement_e2e.cmd"
        checks = @(
            "partner finance dashboard/balance/ledger/payout/document reads return 200",
            "admin settlement snapshot returns 200",
            "canonical partner contracts read returns 200 with items",
            "legacy partner contracts read returns 200 with items",
            "canonical partner settlements read returns 200 with items",
            "legacy partner settlements read returns 200 with items",
            "partner settlement confirm/write tail remains 404"
        )
        finance_org_id = $financeOrgId
        partner_storage_id = $partnerStorageId
        contracts = [ordered]@{
            canonical_status = $coreContractsAlias.StatusCode
            canonical_total = $coreContractsAlias.Json.total
            legacy_status = $legacyContractsAlias.StatusCode
            legacy_total = $legacyContractsAlias.Json.total
        }
        settlements = [ordered]@{
            canonical_status = $coreSettlementAlias.StatusCode
            canonical_total = $coreSettlementAlias.Json.total
            legacy_status = $legacySettlementAlias.StatusCode
            legacy_total = $legacySettlementAlias.Json.total
            confirm_tail_status = $confirmTail.StatusCode
        }
        public_api_change = "additive read-only partner contracts/settlements APIs; settlement write/confirm route remains absent"
    }
    [System.IO.File]::WriteAllText(
        $evidencePath,
        (($evidence | ConvertTo-Json -Depth 12) + [Environment]::NewLine),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Log ("[EVIDENCE] " + $evidencePath)

    Write-Log "E2E_PARTNER_SETTLEMENT: PASS"
} catch {
    $exitCode = 1
    Write-Log ("E2E_PARTNER_SETTLEMENT: FAIL - " + $_.Exception.Message)
}

exit $exitCode
