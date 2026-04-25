$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_partner_trust_e2e"
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

function Invoke-PostgresSql {
    param(
        [string]$Sql,
        [string]$Name,
        [string]$PostgresPassword
    )
    $sqlPath = Join-Path $script:TempDir ($Name + ".sql")
    $outPath = Join-Path $script:TempDir ($Name + ".log")
    [System.IO.File]::WriteAllText($sqlPath, $Sql, [System.Text.UTF8Encoding]::new($false))
    $command = 'docker compose exec -T -e PGPASSWORD="{0}" postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "{1}" > "{2}" 2>&1' -f $PostgresPassword, $sqlPath, $outPath
    Write-Log ("[sql] " + $Name)
    & cmd.exe /c $command
    $exit = $LASTEXITCODE
    $content = if (Test-Path $outPath) { Get-Content -Path $outPath -Raw -ErrorAction SilentlyContinue } else { "" }
    Save-Response -Name ($Name + ".psql.log") -Content $content | Out-Null
    if ($exit -ne 0) {
        throw ("[sql] {0} failed with exit {1}" -f $Name, $exit)
    }
    return $content
}

function Extract-ClientId {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.org -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.org.id)) {
        return [string]$PortalMe.org.id
    }
    if ($null -ne $PortalMe.user -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.user.id)) {
        return [string]$PortalMe.user.id
    }
    if ($null -ne $PortalMe.entitlements_snapshot -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.entitlements_snapshot.org_id)) {
        return [string]$PortalMe.entitlements_snapshot.org_id
    }
    throw "client portal/me did not expose client context id"
}

function Extract-PartnerId {
    param([object]$PortalMe)
    if ($null -ne $PortalMe.partner -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.partner.partner_id)) {
        return [string]$PortalMe.partner.partner_id
    }
    if ($null -ne $PortalMe.org -and -not [string]::IsNullOrWhiteSpace([string]$PortalMe.org.id)) {
        return [string]$PortalMe.org.id
    }
    throw "partner portal/me did not expose partner id"
}

Import-DotEnvDefaults

$baseUrl = Get-Config -Names @("BASE_URL", "GATEWAY_BASE_URL") -Default "http://localhost"
$coreApiBase = Get-Config -Names @("CORE_API_BASE") -Default "http://localhost:8001"
$authUrl = Get-Config -Names @("AUTH_URL") -Default ($baseUrl + "/api/v1/auth")
$coreBase = Get-Config -Names @("CORE_BASE") -Default ($coreApiBase + "/api/core")
$corePortalUrl = Get-Config -Names @("CORE_PORTAL_URL", "CORE_PORTAL") -Default ($coreBase + "/portal")
$clientMarketplaceUrl = Get-Config -Names @("CLIENT_MARKETPLACE_URL", "CORE_CLIENT_MARKETPLACE_URL") -Default ($coreApiBase + "/api/client/marketplace")
$coreClientOrdersUrl = Get-Config -Names @("CORE_MARKETPLACE_CLIENT_ORDERS_URL", "MARKETPLACE_CLIENT_ORDERS_URL") -Default ($coreApiBase + "/api/marketplace/client/orders")
$corePartnerOrdersUrl = Get-Config -Names @("CORE_MARKETPLACE_PARTNER_ORDERS_URL") -Default ($coreBase + "/v1/marketplace/partner/orders")
$corePartnerFinanceUrl = Get-Config -Names @("CORE_PARTNER_URL", "CORE_PARTNER") -Default ($coreBase + "/partner")
$coreAdminMarketplaceUrl = Get-Config -Names @("CORE_ADMIN_MARKETPLACE_URL") -Default ($coreBase + "/v1/admin/marketplace/orders")

$adminEmail = Get-Config -Names @("ADMIN_EMAIL", "NEFT_BOOTSTRAP_ADMIN_EMAIL") -Default "admin@neft.local"
$adminPassword = Get-Config -Names @("ADMIN_PASSWORD", "NEFT_BOOTSTRAP_ADMIN_PASSWORD") -Default "Neft123!"
$clientEmail = Get-Config -Names @("CLIENT_EMAIL", "NEFT_BOOTSTRAP_CLIENT_EMAIL") -Default "client@neft.local"
$clientPassword = Get-Config -Names @("CLIENT_PASSWORD", "NEFT_BOOTSTRAP_CLIENT_PASSWORD") -Default "Client123!"
$partnerEmail = Get-Config -Names @("PARTNER_EMAIL", "NEFT_BOOTSTRAP_PARTNER_EMAIL") -Default "partner@neft.local"
$partnerPassword = Get-Config -Names @("PARTNER_PASSWORD", "NEFT_BOOTSTRAP_PARTNER_PASSWORD") -Default "Partner123!"
$postgresPassword = Get-Config -Names @("POSTGRES_PASSWORD") -Default "change-me"

$exitCode = 0

try {
    Write-Log ("Starting {0}" -f $script:ScriptName)
    Write-Log ("BASE_URL={0}" -f $baseUrl)
    Write-Log ("CORE_CLIENT_ORDERS_URL={0}" -f $coreClientOrdersUrl)
    Write-Log ("CORE_PARTNER_ORDERS_URL={0}" -f $corePartnerOrdersUrl)

    $step = "1_login"
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
        $partnerToken = Login-OrThrow -Step $step -AuthUrl $authUrl -Email $partnerEmail -Password $partnerPassword -Portal "partner" -OutName "partner_login.json"
    }

    $step = "2_portal_context"
    Write-Log ("[{0}] GET {1}/me client" -f $step, $corePortalUrl)
    $clientMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "client_portal_me.json" -Token $clientToken
    Write-Log ("Status: " + $clientMe.StatusCode)
    Assert-Status -Step $step -Actual $clientMe.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($clientMe.Json.actor_type -eq "client") -Message "client actor expected"
    $clientId = Extract-ClientId -PortalMe $clientMe.Json

    Write-Log ("[{0}] GET {1}/me partner" -f $step, $corePortalUrl)
    $partnerMe = Invoke-Api -Method GET -Url ($corePortalUrl + "/me") -OutName "partner_portal_me.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerMe.StatusCode)
    Assert-Status -Step $step -Actual $partnerMe.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($partnerMe.Json.actor_type -eq "partner" -and $partnerMe.Json.access_state -ne "TECH_ERROR") -Message "partner actor must be active enough for marketplace"
    $partnerId = Extract-PartnerId -PortalMe $partnerMe.Json
    Write-Log ("CLIENT_ID={0}" -f $clientId)
    Write-Log ("PARTNER_ID={0}" -f $partnerId)

    $step = "3_seed_catalog"
    $runId = ([guid]::NewGuid().ToString("N")).Substring(0, 10)
    $productId = [guid]::NewGuid().ToString()
    $offerId = [guid]::NewGuid().ToString()
    $proofAttachmentId = [guid]::NewGuid().ToString()
    $category = "smoke-trust-" + $runId
    $seedSql = @"
SET search_path TO processing_core;
INSERT INTO marketplace_partner_profiles (id, partner_id, company_name, description, verification_status, created_at, updated_at)
VALUES (gen_random_uuid(), '$partnerId', 'Smoke Trust Partner $runId', 'Seeded partner profile for trust smoke', 'VERIFIED', now(), now())
ON CONFLICT (partner_id) DO UPDATE
SET company_name = EXCLUDED.company_name, description = EXCLUDED.description, verification_status = 'VERIFIED', updated_at = now();
INSERT INTO marketplace_products (id, partner_id, type, title, description, category, price_model, price_config, status, moderation_status, created_at, updated_at, published_at)
VALUES ('$productId', '$partnerId', 'SERVICE', 'Smoke Trust Product $runId', 'Runtime seeded trust product $runId', '$category', 'FIXED', '{"amount":8900,"currency":"RUB"}'::jsonb, 'PUBLISHED', 'APPROVED', now(), now(), now());
INSERT INTO marketplace_offers (id, partner_id, subject_type, subject_id, title_override, description_override, status, currency, price_model, price_amount, terms, geo_scope, location_ids, entitlement_scope, allowed_subscription_codes, allowed_client_ids, created_at, updated_at)
VALUES ('$offerId', '$partnerId', 'SERVICE', '$productId', 'Smoke Trust Offer $runId', 'Runtime seeded trust offer', 'ACTIVE', 'RUB', 'FIXED', 8900, '{"min_qty":1,"max_qty":1}'::jsonb, 'ALL_PARTNER_LOCATIONS', '[]'::jsonb, 'ALL_CLIENTS', '[]'::jsonb, '[]'::jsonb, now(), now());
"@
    Invoke-PostgresSql -Sql $seedSql -Name "marketplace_trust_seed" -PostgresPassword $postgresPassword | Out-Null

    $step = "4_catalog_visibility"
    Write-Log ("[{0}] GET {1}/products" -f $step, $clientMarketplaceUrl)
    $products = Invoke-Api -Method GET -Url ($clientMarketplaceUrl + "/products") -OutName "products.json" -Token $clientToken
    Write-Log ("Status: " + $products.StatusCode)
    Assert-Status -Step $step -Actual $products.StatusCode -Expected @(200)
    $seededProduct = @(As-List $products.Json.items | Where-Object { [string]$_.id -eq $productId } | Select-Object -First 1)
    Assert-True -Step $step -Condition ($seededProduct.Count -eq 1) -Message "seeded product must be visible to client"

    Write-Log ("[{0}] GET {1}/products/{2}/offers" -f $step, $clientMarketplaceUrl, $productId)
    $offers = Invoke-Api -Method GET -Url ($clientMarketplaceUrl + "/products/" + $productId + "/offers") -OutName "offers.json" -Token $clientToken
    Write-Log ("Status: " + $offers.StatusCode)
    Assert-Status -Step $step -Actual $offers.StatusCode -Expected @(200)
    $seededOffer = @(As-List $offers.Json.items | Where-Object { [string]$_.id -eq $offerId } | Select-Object -First 1)
    Assert-True -Step $step -Condition ($seededOffer.Count -eq 1) -Message "seeded offer must be visible to client"

    $step = "5_order_lifecycle"
    Write-Log ("[{0}] POST {1}" -f $step, $coreClientOrdersUrl)
    $createOrder = Invoke-Api -Method POST -Url $coreClientOrdersUrl -OutName "order_create.json" -Token $clientToken -Body @{
        items = @(@{ offer_id = $offerId; qty = 1 })
        payment_method = "NEFT_INTERNAL"
    }
    Write-Log ("Status: " + $createOrder.StatusCode)
    Assert-Status -Step $step -Actual $createOrder.StatusCode -Expected @(201)
    $orderId = [string]$createOrder.Json.id
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace($orderId) -and $createOrder.Json.status -eq "PENDING_PAYMENT") -Message "order create must return PENDING_PAYMENT id"

    Write-Log ("[{0}] POST {1}/{2}:pay" -f $step, $coreClientOrdersUrl, $orderId)
    $payOrder = Invoke-Api -Method POST -Url ($coreClientOrdersUrl + "/" + $orderId + ":pay") -OutName "order_pay.json" -Token $clientToken -Body @{ payment_method = "NEFT_INTERNAL" }
    Write-Log ("Status: " + $payOrder.StatusCode)
    Assert-Status -Step $step -Actual $payOrder.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($payOrder.Json.status -eq "PAID" -and $payOrder.Json.payment_status -eq "PAID") -Message "order pay must return PAID"

    Write-Log ("[{0}] POST {1}/{2}:confirm" -f $step, $corePartnerOrdersUrl, $orderId)
    $confirmOrder = Invoke-Api -Method POST -Url ($corePartnerOrdersUrl + "/" + $orderId + ":confirm") -OutName "order_confirm.json" -Token $partnerToken
    Write-Log ("Status: " + $confirmOrder.StatusCode)
    Assert-Status -Step $step -Actual $confirmOrder.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($confirmOrder.Json.status -eq "CONFIRMED_BY_PARTNER") -Message "partner confirm must return CONFIRMED_BY_PARTNER"

    Write-Log ("[{0}] POST {1}/{2}/proofs" -f $step, $corePartnerOrdersUrl, $orderId)
    $proof = Invoke-Api -Method POST -Url ($corePartnerOrdersUrl + "/" + $orderId + "/proofs") -OutName "order_proof.json" -Token $partnerToken -Body @{
        attachment_id = $proofAttachmentId
        kind = "PHOTO"
        note = "trust smoke proof"
    }
    Write-Log ("Status: " + $proof.StatusCode)
    Assert-Status -Step $step -Actual $proof.StatusCode -Expected @(201)

    Write-Log ("[{0}] POST {1}/{2}:complete" -f $step, $corePartnerOrdersUrl, $orderId)
    $completeOrder = Invoke-Api -Method POST -Url ($corePartnerOrdersUrl + "/" + $orderId + ":complete") -OutName "order_complete.json" -Token $partnerToken -Body @{
        comment = "trust smoke complete"
    }
    Write-Log ("Status: " + $completeOrder.StatusCode)
    Assert-Status -Step $step -Actual $completeOrder.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($completeOrder.Json.status -eq "COMPLETED") -Message "partner complete must return COMPLETED"

    $step = "6_settlement_snapshot"
    Write-Log ("[{0}] GET {1}/{2}/settlement-snapshot" -f $step, $coreAdminMarketplaceUrl, $orderId)
    $snapshot = Invoke-Api -Method GET -Url ($coreAdminMarketplaceUrl + "/" + $orderId + "/settlement-snapshot") -OutName "admin_settlement_snapshot.json" -Token $adminToken
    Write-Log ("Status: " + $snapshot.StatusCode)
    Assert-Status -Step $step -Actual $snapshot.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($snapshot.Json.order_id -eq $orderId -and -not [string]::IsNullOrWhiteSpace([string]$snapshot.Json.hash)) -Message "complete order must create settlement snapshot"

    Write-Log ("[{0}] POST {1}/{2}/settlement-override" -f $step, $coreAdminMarketplaceUrl, $orderId)
    $override = Invoke-Api -Method POST -Url ($coreAdminMarketplaceUrl + "/" + $orderId + "/settlement-override") -OutName "admin_settlement_override.json" -Token $adminToken -Body @{
        gross_amount = $snapshot.Json.gross_amount
        platform_fee = $snapshot.Json.platform_fee
        penalties = $snapshot.Json.penalties
        partner_net = $snapshot.Json.partner_net
        currency = $snapshot.Json.currency
        reason = "smoke trust finalize"
    }
    Write-Log ("Status: " + $override.StatusCode)
    Assert-Status -Step $step -Actual $override.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace([string]$override.Json.finalized_at)) -Message "settlement override must finalize snapshot"

    $step = "7_partner_explain"
    Write-Log ("[{0}] GET {1}/{2}/settlement" -f $step, $corePartnerOrdersUrl, $orderId)
    $partnerSettlement = Invoke-Api -Method GET -Url ($corePartnerOrdersUrl + "/" + $orderId + "/settlement") -OutName "partner_order_settlement.json" -Token $partnerToken
    Write-Log ("Status: " + $partnerSettlement.StatusCode)
    Assert-Status -Step $step -Actual $partnerSettlement.StatusCode -Expected @(200)
    Assert-True -Step $step -Condition ($partnerSettlement.Json.order_id -eq $orderId -and -not [string]::IsNullOrWhiteSpace([string]$partnerSettlement.Json.snapshot.hash)) -Message "partner settlement must expose finalized snapshot hash"

    Write-Log ("[{0}] GET {1}/ledger?limit=100" -f $step, $corePartnerFinanceUrl)
    $ledger = Invoke-Api -Method GET -Url ($corePartnerFinanceUrl + "/ledger?limit=100") -OutName "partner_ledger.json" -Token $partnerToken
    Write-Log ("Status: " + $ledger.StatusCode)
    Assert-Status -Step $step -Actual $ledger.StatusCode -Expected @(200, 403)
    if ($ledger.StatusCode -eq 200) {
        $entry = @(As-List $ledger.Json.items | Where-Object { [string]$_.order_id -eq $orderId -and [string]$_.entry_type -eq "EARNED" } | Select-Object -First 1)
        Assert-True -Step $step -Condition ($entry.Count -eq 1) -Message "partner ledger must include earned entry for order"
        $entryId = [string]$entry[0].id

        Write-Log ("[{0}] GET {1}/ledger/{2}/explain" -f $step, $corePartnerFinanceUrl, $entryId)
        $explain = Invoke-Api -Method GET -Url ($corePartnerFinanceUrl + "/ledger/" + $entryId + "/explain") -OutName "ledger_explain.json" -Token $partnerToken
        Write-Log ("Status: " + $explain.StatusCode)
        Assert-Status -Step $step -Actual $explain.StatusCode -Expected @(200)
        Assert-True -Step $step -Condition ($explain.Json.source_id -eq $orderId -and -not [string]::IsNullOrWhiteSpace([string]$explain.Json.formula)) -Message "ledger explain must reference order and formula"
        $breakdownUrl = [string]$explain.Json.settlement_breakdown_url
        Assert-True -Step $step -Condition ($breakdownUrl -eq ("/api/core/v1/marketplace/partner/orders/" + $orderId + "/settlement")) -Message "ledger explain must return canonical settlement URL"
        $breakdown = Invoke-Api -Method GET -Url ($coreApiBase + $breakdownUrl) -OutName "ledger_breakdown_url.json" -Token $partnerToken
        Write-Log ("Status: " + $breakdown.StatusCode)
        Assert-Status -Step $step -Actual $breakdown.StatusCode -Expected @(200)
    } else {
        Assert-True -Step $step -Condition ($ledger.Content -match "missing_capability.*PARTNER_FINANCE_VIEW|PARTNER_FINANCE_VIEW.*missing_capability") -Message "finance ledger must fail explicitly for non-finance partner"
        Write-Log ("[{0}] finance ledger access limited by capability; partner order settlement remains the trust explain surface" -f $step)
    }

    $step = "8_export_chain"
    $today = (Get-Date).ToString("yyyy-MM-dd")
    Write-Log ("[{0}] POST {1}/exports/settlement-chain" -f $step, $corePartnerFinanceUrl)
    $export = Invoke-Api -Method POST -Url ($corePartnerFinanceUrl + "/exports/settlement-chain") -OutName "export_settlement_chain.json" -Token $partnerToken -Body @{
        "from" = $today
        to = $today
        format = "CSV"
    }
    Write-Log ("Status: " + $export.StatusCode)
    Assert-Status -Step $step -Actual $export.StatusCode -Expected @(201, 403, 503)
    if ($export.StatusCode -eq 201) {
        Assert-True -Step $step -Condition (-not [string]::IsNullOrWhiteSpace([string]$export.Json.id)) -Message "export job response must include id"
    } elseif ($export.StatusCode -eq 403) {
        Assert-True -Step $step -Condition ($export.Content -match "missing_capability.*PARTNER_FINANCE_VIEW|PARTNER_FINANCE_VIEW.*missing_capability") -Message "settlement-chain export must fail explicitly for non-finance partner"
    } else {
        Assert-True -Step $step -Condition ($export.Content -match "celery_not_available") -Message "degraded export must be explicit"
    }

    Write-Log "E2E_PARTNER_TRUST: PASS"
} catch {
    $exitCode = 1
    Write-Log ("E2E_PARTNER_TRUST: FAIL - " + $_.Exception.Message)
}

exit $exitCode
