$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_commerce_overdue_unblock_e2e"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:RunTs = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogDir = Join-Path $script:RepoRoot "logs"
$script:TempDir = Join-Path $env:TEMP ($script:ScriptName + "_" + $script:RunTs)
$script:LogFile = Join-Path $script:LogDir ("smoke_commerce_unblock_" + $script:RunTs + ".log")
$script:FailedStep = $null

New-Item -ItemType Directory -Force -Path $script:LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $script:TempDir | Out-Null

function Write-Log {
    param([string]$Message)
    Write-Host $Message
    Add-Content -Path $script:LogFile -Value $Message
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
    if ($Token) {
        $headers["Authorization"] = if ($Token.StartsWith("Bearer ")) { $Token } else { "Bearer $Token" }
    }

    $contentType = "application/json"
    $bodyJson = $null
    if ($null -ne $Body) {
        $bodyJson = $Body | ConvertTo-Json -Compress -Depth 10
    }

    try {
        if ($null -ne $bodyJson) {
            $response = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers -ContentType $contentType -Body $bodyJson -UseBasicParsing
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
        $reader = New-Object System.IO.StreamReader($webResponse.GetResponseStream())
        $content = $reader.ReadToEnd()
        $reader.Dispose()
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
    if ($Expected -contains $Actual) {
        return
    }
    throw ("[{0}] expected status {1} got {2}" -f $Step, ($Expected -join "/"), $Actual)
}

function Assert-Contains {
    param(
        [string]$Step,
        [string]$Content,
        [string[]]$Needles
    )
    foreach ($needle in $Needles) {
        if ($Content -like ("*" + $needle + "*")) {
            return
        }
    }
    throw ("[{0}] expected body to contain one of: {1}" -f $Step, ($Needles -join ", "))
}

function Get-JwtClaim {
    param(
        [string]$Token,
        [string]$Claim
    )

    if (-not $Token) {
        return $null
    }
    $rawToken = if ($Token.StartsWith("Bearer ")) { $Token.Substring(7) } else { $Token }
    $parts = $rawToken.Split(".")
    if ($parts.Length -lt 2) {
        return $null
    }
    $payload = $parts[1].Replace("-", "+").Replace("_", "/")
    switch ($payload.Length % 4) {
        2 { $payload += "==" }
        3 { $payload += "=" }
    }
    $jsonText = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload))
    $json = $jsonText | ConvertFrom-Json
    return $json.$Claim
}

function Expand-Items {
    param([object]$Payload)
    $items = @()
    if ($null -eq $Payload) {
        return $items
    }
    if ($Payload -is [System.Array]) {
        return @($Payload)
    }
    if ($null -ne $Payload.items) { $items += @($Payload.items) }
    if ($null -ne $Payload.results) { $items += @($Payload.results) }
    if ($null -ne $Payload.data) { $items += @($Payload.data) }
    return $items
}

function Select-Invoice {
    param([object]$Payload)
    $items = Expand-Items $Payload
    foreach ($item in $items) {
        $status = [string]$item.status
        if ($status -in @("ISSUED", "OVERDUE")) {
            return $item
        }
    }
    return $null
}

function Select-PendingPaymentIntake {
    param([object]$Payload)
    $items = Expand-Items $Payload
    $sorted = @($items | Sort-Object -Property created_at -Descending)
    foreach ($item in $sorted) {
        $status = [string]$item.status
        if ($status -in @("SUBMITTED", "UNDER_REVIEW")) {
            return $item
        }
    }
    return $null
}

function Get-InvoiceAmount {
    param([object]$Invoice)
    foreach ($propertyName in @("amount_due", "total", "amount", "total_amount")) {
        $value = $Invoice.$propertyName
        if ($null -ne $value -and "$value".Trim() -ne "") {
            return [decimal]::Parse([string]$value, [System.Globalization.CultureInfo]::InvariantCulture)
        }
    }
    return $null
}

function Get-PortalEntitlementsHash {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.entitlements_hash) {
        return [string]$PortalMe.entitlements_hash
    }
    if ($null -ne $PortalMe.entitlements_snapshot -and $null -ne $PortalMe.entitlements_snapshot.computed) {
        return [string]$PortalMe.entitlements_snapshot.computed.hash
    }
    return ""
}

function Get-PortalEntitlementsComputedAt {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.entitlements_computed_at) {
        return [string]$PortalMe.entitlements_computed_at
    }
    if ($null -ne $PortalMe.entitlements_snapshot -and $null -ne $PortalMe.entitlements_snapshot.computed) {
        return [string]$PortalMe.entitlements_snapshot.computed.computed_at
    }
    return ""
}

function Has-CommercialPortalContext {
    param([object]$PortalMe)
    if ($null -eq $PortalMe) {
        return $false
    }
    if ($null -eq $PortalMe.org) {
        return $false
    }
    if ($null -eq $PortalMe.subscription) {
        return $false
    }
    return $true
}

function Ensure-DemoCoreSeed {
    $seedScript = Join-Path $PSScriptRoot "seed.cmd"
    if (-not (Test-Path $seedScript)) {
        throw "demo core seed script not found"
    }
    Write-Log "[seed] cmd /c scripts\seed.cmd"
    & cmd.exe /c $seedScript | ForEach-Object { Write-Log $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "demo core seed failed"
    }
}

function Resolve-PlanCode {
    param(
        [string]$RequestedPlanCode,
        [string]$OrgType,
        [string]$AdminToken,
        [string]$CoreApiBase,
        [string]$CoreBase
    )

    $plansResponse = Invoke-Api -Method GET -Url ($CoreApiBase + $CoreBase + "/subscriptions/plans") -OutName "subscriptions_plans.json" -Token $AdminToken
    Assert-Status -Step "resolve_plan_code" -Actual $plansResponse.StatusCode -Expected @(200)
    $plans = Expand-Items $plansResponse.Json
    if (-not $plans.Count) {
        throw "resolve_plan_code: no subscription plans returned"
    }

    $isInvoiceCompatiblePaidPlan = {
        param([object]$Plan)
        if ($null -eq $Plan -or $null -eq $Plan.price_cents) {
            return $false
        }
        try {
            $priceCents = [int64]$Plan.price_cents
            return $priceCents -gt 0 -and ($priceCents % 100) -eq 0
        } catch {
            return $false
        }
    }

    $exact = $plans | Where-Object { [string]$_.code -eq $RequestedPlanCode -and (& $isInvoiceCompatiblePaidPlan $_) } | Select-Object -First 1
    if ($null -ne $exact) {
        return [string]$exact.code
    }

    $candidates = @($plans | Where-Object { $_.is_active -eq $true -and [string]$_.code -like ($RequestedPlanCode + "_*") -and (& $isInvoiceCompatiblePaidPlan $_) })
    if (-not $candidates.Count) {
        return ""
    }

    $priority = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($OrgType)) {
        $normalizedOrgType = $OrgType.ToUpper().Replace("-", "_")
        foreach ($suffix in @("1M", "6M", "12M")) {
            $priority.Add($RequestedPlanCode + "_" + $normalizedOrgType + "_" + $suffix)
        }
    }
    foreach ($code in @(
        $RequestedPlanCode + "_SMB_FLEET_1M",
        $RequestedPlanCode + "_INDIVIDUAL_1M",
        $RequestedPlanCode + "_SELF_EMPLOYED_1M",
        $RequestedPlanCode + "_ENTERPRISE_1M",
        $RequestedPlanCode + "_SMB_FLEET_6M",
        $RequestedPlanCode + "_INDIVIDUAL_6M",
        $RequestedPlanCode + "_SELF_EMPLOYED_6M",
        $RequestedPlanCode + "_ENTERPRISE_6M",
        $RequestedPlanCode + "_SMB_FLEET_12M",
        $RequestedPlanCode + "_INDIVIDUAL_12M",
        $RequestedPlanCode + "_SELF_EMPLOYED_12M",
        $RequestedPlanCode + "_ENTERPRISE_12M"
    )) {
        if (-not $priority.Contains($code)) {
            $priority.Add($code)
        }
    }

    foreach ($code in $priority) {
        $match = $candidates | Where-Object { [string]$_.code -eq $code } | Select-Object -First 1
        if ($null -ne $match) {
            return [string]$match.code
        }
    }

    $fallback = $candidates | Sort-Object -Property billing_period_months, price_cents | Select-Object -First 1
    if ($null -ne $fallback) {
        return [string]$fallback.code
    }
    return ""
}

function Wait-ForHealth {
    param([string]$HealthUrl)
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $response = Invoke-Api -Method GET -Url $HealthUrl -OutName ("health_wait_" + $attempt + ".json")
        if ($response.StatusCode -eq 200 -and $response.Content -like '*"status":"ok"*') {
            return
        }
        Start-Sleep -Seconds 2
    }
    throw ("wait_for_health failed for " + $HealthUrl)
}

function Cleanup-State {
    param(
        [string]$AdminToken,
        [string]$CoreAdminUrl,
        [string]$OrgId
    )
    if (-not $AdminToken -or -not $OrgId) {
        return
    }

    Write-Log "[cleanup] POST commercial status ACTIVE"
    $statusResponse = Invoke-Api -Method POST -Url ($CoreAdminUrl + "/commercial/orgs/" + $OrgId + "/status") -OutName "cleanup_status_active.json" -Token $AdminToken -Body @{
        status = "ACTIVE"
        reason = "smoke_commerce_cleanup"
    }
    Write-Log ("Status: " + $statusResponse.StatusCode)

    Write-Log "[cleanup] POST entitlements recompute"
    $entitlementsResponse = Invoke-Api -Method POST -Url ($CoreAdminUrl + "/commercial/orgs/" + $OrgId + "/entitlements/recompute") -OutName "cleanup_entitlements_recompute.json" -Token $AdminToken -Body @{}
    Write-Log ("Status: " + $entitlementsResponse.StatusCode)
}

$authHostBase = if ($env:AUTH_HOST_BASE) { $env:AUTH_HOST_BASE } else { "http://localhost:8002" }
$coreApiBase = if ($env:CORE_API_BASE) { $env:CORE_API_BASE } else { "http://localhost:8001" }
$authBase = if ($env:AUTH_BASE) { $env:AUTH_BASE } else { "/api/v1/auth" }
$coreBase = if ($env:CORE_BASE) { $env:CORE_BASE } else { "/api/core" }
$authUrl = if ($env:AUTH_URL) { $env:AUTH_URL } else { $authHostBase + $authBase }
$coreClientUrl = if ($env:CORE_CLIENT_URL) { $env:CORE_CLIENT_URL } else { $coreApiBase + $coreBase + "/client" }
$corePortalUrl = if ($env:CORE_PORTAL_URL) { $env:CORE_PORTAL_URL } else { $coreApiBase + $coreBase + "/portal" }
$coreAdminUrl = if ($env:CORE_ADMIN_URL) { $env:CORE_ADMIN_URL } else { $coreApiBase + $coreBase + "/v1/admin" }

$adminEmail = if ($env:ADMIN_EMAIL) { $env:ADMIN_EMAIL } else { "admin@neft.local" }
$adminPassword = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "Neft123!" }
$clientEmail = if ($env:CLIENT_EMAIL) { $env:CLIENT_EMAIL } else { "client@neft.local" }
$clientPassword = if ($env:CLIENT_PASSWORD) { $env:CLIENT_PASSWORD } else { "Client123!" }
$requestedPlanCode = if ($env:PLAN_CODE) { $env:PLAN_CODE } else { "CONTROL" }
$planVersion = if ($env:PLAN_VERSION) { [int]$env:PLAN_VERSION } else { 1 }
$payerName = if ($env:PAYER_NAME) { $env:PAYER_NAME } else { "OOO Romashka" }
$payerInn = if ($env:PAYER_INN) { $env:PAYER_INN } else { "7700000000" }
$bankRef = if ($env:BANK_REF) { $env:BANK_REF } else { "SMOKE-REF-1" }
$paymentAmountOverride = $env:PAYMENT_AMOUNT

$adminToken = ""
$clientToken = ""
$orgId = if ($env:ORG_ID) { [string]$env:ORG_ID } else { "" }

try {
    $step = "0_health"
    Write-Log ("[{0}] GET {1}/health" -f $step, $coreApiBase)
    Wait-ForHealth -HealthUrl ($coreApiBase + "/health")
    $healthResponse = Invoke-Api -Method GET -Url ($coreApiBase + "/health") -OutName "health.json"
    Write-Log ("Status: " + $healthResponse.StatusCode)
    Assert-Status -Step $step -Actual $healthResponse.StatusCode -Expected @(200)
    Assert-Contains -Step $step -Content $healthResponse.Content -Needles @('"status":"ok"')

    $step = "0_admin_login"
    Write-Log ("[{0}] POST {1}/login" -f $step, $authUrl)
    $adminLogin = Invoke-Api -Method POST -Url ($authUrl + "/login") -OutName "admin_login.json" -Body @{
        email = $adminEmail
        password = $adminPassword
        portal = "admin"
    }
    Write-Log ("Status: " + $adminLogin.StatusCode)
    Assert-Status -Step $step -Actual $adminLogin.StatusCode -Expected @(200)
    $adminToken = [string]$adminLogin.Json.access_token
    if (-not $adminToken) {
        throw "admin login did not return access_token"
    }

    Write-Log ("[{0}] GET {1}{2}/admin/auth/verify" -f $step, $coreApiBase, $coreBase)
    $adminVerify = Invoke-Api -Method GET -Url ($coreApiBase + $coreBase + "/admin/auth/verify") -OutName "admin_verify.txt" -Token $adminToken
    Write-Log ("Status: " + $adminVerify.StatusCode)
    Assert-Status -Step $step -Actual $adminVerify.StatusCode -Expected @(204)

    $step = "1_client_login"
    Write-Log ("[{0}] POST {1}/login" -f $step, $authUrl)
    $clientLogin = Invoke-Api -Method POST -Url ($authUrl + "/login") -OutName "client_login.json" -Body @{
        email = $clientEmail
        password = $clientPassword
        portal = "client"
    }
    Write-Log ("Status: " + $clientLogin.StatusCode)
    Assert-Status -Step $step -Actual $clientLogin.StatusCode -Expected @(200)
    $clientToken = [string]$clientLogin.Json.access_token
    if (-not $clientToken) {
        throw "client login did not return access_token"
    }

    Write-Log ("[{0}] GET {1}{2}/client/auth/verify" -f $step, $coreApiBase, $coreBase)
    $clientVerify = Invoke-Api -Method GET -Url ($coreApiBase + $coreBase + "/client/auth/verify") -OutName "client_verify.txt" -Token $clientToken
    Write-Log ("Status: " + $clientVerify.StatusCode)
    Assert-Status -Step $step -Actual $clientVerify.StatusCode -Expected @(204)

    Write-Log ("[{0}] GET {1}/me" -f $step, $corePortalUrl)
    $portalMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "portal_me.json" -Token $clientToken
    Write-Log ("Status: " + $portalMe.StatusCode)
    Assert-Status -Step $step -Actual $portalMe.StatusCode -Expected @(200)
    if (-not (Has-CommercialPortalContext -PortalMe $portalMe.Json)) {
        Ensure-DemoCoreSeed
        Write-Log ("[{0}] GET {1}/me (after seed)" -f $step, $corePortalUrl)
        $portalMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "portal_me_after_seed.json" -Token $clientToken
        Write-Log ("Status: " + $portalMe.StatusCode)
        Assert-Status -Step $step -Actual $portalMe.StatusCode -Expected @(200)
    }
    if (-not (Has-CommercialPortalContext -PortalMe $portalMe.Json)) {
        throw "client portal me did not expose seeded commercial context"
    }

    if (-not $orgId) { $orgId = [string](Get-JwtClaim -Token $clientToken -Claim "org_id") }
    if (-not $orgId) { $orgId = [string](Get-JwtClaim -Token $clientToken -Claim "tenant_id") }
    if (-not $orgId -and $null -ne $portalMe.Json.entitlements_snapshot) { $orgId = [string]$portalMe.Json.entitlements_snapshot.org_id }
    if (-not $orgId -and $null -ne $portalMe.Json.org) { $orgId = [string]$portalMe.Json.org.id }
    if (-not $orgId) {
        throw "client portal me did not expose org id"
    }

    $entHashBefore = Get-PortalEntitlementsHash -PortalMe $portalMe.Json
    $entCompBefore = Get-PortalEntitlementsComputedAt -PortalMe $portalMe.Json
    $subStatusBefore = [string]$portalMe.Json.subscription.status
    $orgType = [string]$portalMe.Json.org.org_type
    $planCode = Resolve-PlanCode -RequestedPlanCode $requestedPlanCode -OrgType $orgType -AdminToken $adminToken -CoreApiBase $coreApiBase -CoreBase $coreBase
    if (-not $planCode) {
        throw ("no compatible plan resolved for " + $requestedPlanCode)
    }
    Write-Log ("ORG_ID=" + $orgId)
    Write-Log ("ENT_HASH_BEFORE=" + $entHashBefore)
    Write-Log ("SUB_STATUS_BEFORE=" + $subStatusBefore)
    Write-Log ("Resolved PLAN_CODE={0} (requested {1}, org_type={2})" -f $planCode, $requestedPlanCode, $orgType)

    $step = "2_ensure_subscription_active"
    Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/plan" -f $step, $coreAdminUrl, $orgId)
    $planResponse = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/plan") -OutName "plan_setup.json" -Token $adminToken -Body @{
        plan_code = $planCode
        plan_version = $planVersion
        billing_cycle = "MONTHLY"
        status = "ACTIVE"
        reason = "smoke_commerce_plan_setup"
    }
    Write-Log ("Status: " + $planResponse.StatusCode)
    Assert-Status -Step $step -Actual $planResponse.StatusCode -Expected @(200)

    if ($subStatusBefore -ne "ACTIVE") {
        Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/status" -f $step, $coreAdminUrl, $orgId)
        $statusSetupResponse = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/status") -OutName "status_active_setup.json" -Token $adminToken -Body @{
            status = "ACTIVE"
            reason = "smoke_commerce_overdue_setup"
        }
        Write-Log ("Status: " + $statusSetupResponse.StatusCode)
        Assert-Status -Step $step -Actual $statusSetupResponse.StatusCode -Expected @(200)

        Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/entitlements/recompute" -f $step, $coreAdminUrl, $orgId)
        $recomputeSetupResponse = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/entitlements/recompute") -OutName "entitlements_recompute_setup.json" -Token $adminToken -Body @{}
        Write-Log ("Status: " + $recomputeSetupResponse.StatusCode)
        Assert-Status -Step $step -Actual $recomputeSetupResponse.StatusCode -Expected @(200)
    }

    Write-Log ("[{0}] GET {1}/me" -f $step, $corePortalUrl)
    $portalMeActive = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "portal_me_active.json" -Token $clientToken
    Write-Log ("Status: " + $portalMeActive.StatusCode)
    Assert-Status -Step $step -Actual $portalMeActive.StatusCode -Expected @(200)
    if ([string]$portalMeActive.Json.subscription.status -ne "ACTIVE") {
        throw ("[{0}] expected subscription ACTIVE" -f $step)
    }

    $step = "3_find_or_generate_invoice"
    Write-Log ("[{0}] GET {1}/invoices?limit=20" -f $step, $coreClientUrl)
    $invoiceListBefore = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices?limit=20") -OutName "invoices_list_before_generate.json" -Token $clientToken
    Write-Log ("Status: " + $invoiceListBefore.StatusCode)
    Assert-Status -Step $step -Actual $invoiceListBefore.StatusCode -Expected @(200)
    $invoice = Select-Invoice -Payload $invoiceListBefore.Json
    if ($null -eq $invoice) {
        $baseDate = Get-Date
        $targetDates = @()
        for ($monthOffset = 0; $monthOffset -lt 12; $monthOffset++) {
            $targetDates += $baseDate.AddMonths($monthOffset).ToString("yyyy-MM-dd")
        }
        $attemptIndex = 0
        foreach ($targetDate in $targetDates) {
            Write-Log ("[{0}] POST {1}/billing/generate (target_date={2})" -f $step, $coreAdminUrl, $targetDate)
            $generateResponse = Invoke-Api -Method POST -Url ($coreAdminUrl + "/billing/generate") -OutName ("invoice_generate_" + $attemptIndex + ".json") -Token $adminToken -Body @{
                org_id = [int]$orgId
                target_date = $targetDate
            }
            Write-Log ("Status: " + $generateResponse.StatusCode)
            Assert-Status -Step $step -Actual $generateResponse.StatusCode -Expected @(200)

            $invoiceIdCandidates = @()
            if ($null -ne $generateResponse.Json.invoice_ids) { $invoiceIdCandidates += @($generateResponse.Json.invoice_ids) }
            if ($null -ne $generateResponse.Json.created_ids) { $invoiceIdCandidates += @($generateResponse.Json.created_ids) }
            if ($invoiceIdCandidates.Count -gt 0) {
                $generatedInvoiceId = [string]$invoiceIdCandidates[0]
                $detailResponse = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices/" + $generatedInvoiceId) -OutName ("invoice_detail_generated_" + $attemptIndex + ".json") -Token $clientToken
                Write-Log ("Status: " + $detailResponse.StatusCode)
                Assert-Status -Step $step -Actual $detailResponse.StatusCode -Expected @(200)
                $invoice = $detailResponse.Json
            } else {
                Write-Log ("[{0}] GET {1}/invoices?limit=20 (after generate target_date={2})" -f $step, $coreClientUrl, $targetDate)
                $invoiceListAfter = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices?limit=20") -OutName ("invoices_list_after_generate_" + $attemptIndex + ".json") -Token $clientToken
                Write-Log ("Status: " + $invoiceListAfter.StatusCode)
                Assert-Status -Step $step -Actual $invoiceListAfter.StatusCode -Expected @(200)
                $invoice = Select-Invoice -Payload $invoiceListAfter.Json
            }
            if ($null -ne $invoice) {
                break
            }
            $attemptIndex += 1
        }
    }

    if ($null -eq $invoice) {
        throw ("[{0}] no issued or overdue invoice found" -f $step)
    }
    $invoiceId = [string]$invoice.id
    $invoiceTotal = Get-InvoiceAmount -Invoice $invoice
    if ($null -eq $invoiceTotal) {
        Write-Log ("[{0}] GET {1}/invoices/{2}" -f $step, $coreClientUrl, $invoiceId)
        $invoiceDetail = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices/" + $invoiceId) -OutName "invoice_detail.json" -Token $clientToken
        Write-Log ("Status: " + $invoiceDetail.StatusCode)
        Assert-Status -Step $step -Actual $invoiceDetail.StatusCode -Expected @(200)
        $invoiceTotal = Get-InvoiceAmount -Invoice $invoiceDetail.Json
    }
    if ($null -eq $invoiceTotal) {
        throw ("[{0}] invoice total not resolved" -f $step)
    }
    $paymentAmount = if ($paymentAmountOverride) { [decimal]::Parse($paymentAmountOverride, [System.Globalization.CultureInfo]::InvariantCulture) } else { $invoiceTotal }
    Write-Log ("INVOICE_ID=" + $invoiceId)

    $step = "4_force_overdue"
    Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/status" -f $step, $coreAdminUrl, $orgId)
    $statusOverdue = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/status") -OutName "status_overdue.json" -Token $adminToken -Body @{
        status = "OVERDUE"
        reason = "smoke_commerce_overdue"
    }
    Write-Log ("Status: " + $statusOverdue.StatusCode)
    Assert-Status -Step $step -Actual $statusOverdue.StatusCode -Expected @(200)

    Write-Log ("[{0}] POST {1}/commercial/orgs/{2}/entitlements/recompute" -f $step, $coreAdminUrl, $orgId)
    $recomputeOverdue = Invoke-Api -Method POST -Url ($coreAdminUrl + "/commercial/orgs/" + $orgId + "/entitlements/recompute") -OutName "entitlements_recompute_overdue.json" -Token $adminToken -Body @{}
    Write-Log ("Status: " + $recomputeOverdue.StatusCode)
    Assert-Status -Step $step -Actual $recomputeOverdue.StatusCode -Expected @(200)

    Write-Log ("[{0}] POST {1}/exports/jobs (expect 403)" -f $step, $coreClientUrl)
    $exportBlocked = Invoke-Api -Method POST -Url ($coreClientUrl + "/exports/jobs") -OutName "export_blocked.json" -Token $clientToken -Body @{
        report_type = "cards"
        format = "CSV"
        filters = @{}
    }
    Write-Log ("Status: " + $exportBlocked.StatusCode)
    Assert-Status -Step $step -Actual $exportBlocked.StatusCode -Expected @(403)
    if (-not [string]::IsNullOrWhiteSpace($exportBlocked.Content)) {
        Assert-Contains -Step $step -Content $exportBlocked.Content -Needles @("billing_soft_blocked", "subscription_overdue")
    }

    $step = "4_prepare_payment_intake"
    Write-Log ("[{0}] GET {1}/invoices/{2}/payment-intakes" -f $step, $coreClientUrl, $invoiceId)
    $paymentIntakesBefore = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices/" + $invoiceId + "/payment-intakes") -OutName "payment_intakes_before_submit.json" -Token $clientToken
    Write-Log ("Status: " + $paymentIntakesBefore.StatusCode)
    Assert-Status -Step $step -Actual $paymentIntakesBefore.StatusCode -Expected @(200)
    $pendingIntake = Select-PendingPaymentIntake -Payload $paymentIntakesBefore.Json
    if ($null -ne $pendingIntake) {
        Write-Log ("[{0}] POST {1}/billing/payment-intakes/{2}/reject" -f $step, $coreAdminUrl, $pendingIntake.id)
        $rejectPending = Invoke-Api -Method POST -Url ($coreAdminUrl + "/billing/payment-intakes/" + [string]$pendingIntake.id + "/reject") -OutName "payment_intake_reset.json" -Token $adminToken -Body @{
            review_note = "smoke_reset_pending_intake"
        }
        Write-Log ("Status: " + $rejectPending.StatusCode)
        Assert-Status -Step $step -Actual $rejectPending.StatusCode -Expected @(200, 201)
    }

    $step = "5_payment_intake"
    $paidAt = Get-Date -Format "yyyy-MM-dd"
    Write-Log ("[{0}] POST {1}/invoices/{2}/payment-intakes" -f $step, $coreClientUrl, $invoiceId)
    $paymentIntakeResponse = Invoke-Api -Method POST -Url ($coreClientUrl + "/invoices/" + $invoiceId + "/payment-intakes") -OutName "payment_intake.json" -Token $clientToken -Body @{
        amount = $paymentAmount
        currency = "RUB"
        payer_name = $payerName
        payer_inn = $payerInn
        bank_reference = $bankRef
        paid_at_claimed = $paidAt
        comment = "smoke_e2e_payment_intake"
    }
    Write-Log ("Status: " + $paymentIntakeResponse.StatusCode)
    Assert-Status -Step $step -Actual $paymentIntakeResponse.StatusCode -Expected @(200, 201)
    $paymentIntakeId = [string]$paymentIntakeResponse.Json.id
    if (-not $paymentIntakeId) {
        $paymentIntakeId = [string]$paymentIntakeResponse.Json.payment_intake_id
    }
    if (-not $paymentIntakeId) {
        throw ("[{0}] payment intake id not found" -f $step)
    }

    $step = "6_admin_approve"
    Write-Log ("[{0}] POST {1}/billing/payment-intakes/{2}/approve" -f $step, $coreAdminUrl, $paymentIntakeId)
    $approveResponse = Invoke-Api -Method POST -Url ($coreAdminUrl + "/billing/payment-intakes/" + $paymentIntakeId + "/approve") -OutName "payment_approve.json" -Token $adminToken -Body @{
        review_note = "smoke_e2e_approve"
    }
    Write-Log ("Status: " + $approveResponse.StatusCode)
    Assert-Status -Step $step -Actual $approveResponse.StatusCode -Expected @(200, 201)

    Write-Log ("[{0}] GET {1}/invoices/{2}" -f $step, $coreClientUrl, $invoiceId)
    $invoiceAfter = Invoke-Api -Method GET -Url ($coreClientUrl + "/invoices/" + $invoiceId) -OutName "invoice_after.json" -Token $clientToken
    Write-Log ("Status: " + $invoiceAfter.StatusCode)
    Assert-Status -Step $step -Actual $invoiceAfter.StatusCode -Expected @(200)
    Assert-Contains -Step $step -Content $invoiceAfter.Content -Needles @("PAID")

    Write-Log ("[{0}] GET {1}/me" -f $step, $corePortalUrl)
    $portalMeAfter = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "portal_me_after.json" -Token $clientToken
    Write-Log ("Status: " + $portalMeAfter.StatusCode)
    Assert-Status -Step $step -Actual $portalMeAfter.StatusCode -Expected @(200)
    $subStatusAfter = [string]$portalMeAfter.Json.subscription.status
    if ($subStatusAfter -ne "ACTIVE") {
        throw ("[{0}] expected subscription ACTIVE after unblock" -f $step)
    }
    $entHashAfter = Get-PortalEntitlementsHash -PortalMe $portalMeAfter.Json
    $entCompAfter = Get-PortalEntitlementsComputedAt -PortalMe $portalMeAfter.Json
    if (($entHashBefore -eq $entHashAfter) -and ($entCompBefore -eq $entCompAfter)) {
        throw ("[{0}] entitlements hash/computed_at did not change after unblock" -f $step)
    }

    $step = "7_exports_unblocked"
    Write-Log ("[{0}] POST {1}/exports/jobs" -f $step, $coreClientUrl)
    $exportUnblocked = Invoke-Api -Method POST -Url ($coreClientUrl + "/exports/jobs") -OutName "export_unblocked.json" -Token $clientToken -Body @{
        report_type = "cards"
        format = "CSV"
        filters = @{}
    }
    Write-Log ("Status: " + $exportUnblocked.StatusCode)
    Assert-Status -Step $step -Actual $exportUnblocked.StatusCode -Expected @(200, 201)

    Write-Log "E2E_COMMERCE_UNBLOCK: PASS"
    exit 0
} catch {
    $script:FailedStep = if ($step) { $step } else { "unknown" }
    Write-Log ("[FAIL] " + $_.Exception.Message)
    Write-Log ("E2E_COMMERCE_UNBLOCK: FAIL at " + $script:FailedStep)
    exit 1
} finally {
    Cleanup-State -AdminToken $adminToken -CoreAdminUrl $coreAdminUrl -OrgId $orgId
}
