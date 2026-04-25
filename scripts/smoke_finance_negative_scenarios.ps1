$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_finance_negative_scenarios"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:RunTs = Get-Date -Format "yyyyMMdd_HHmmss"
$script:TempDir = Join-Path $env:TEMP ($script:ScriptName + "_" + $script:RunTs)
New-Item -ItemType Directory -Force -Path $script:TempDir | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host $Message
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

    $bodyJson = $null
    if ($null -ne $Body) {
        $bodyJson = $Body | ConvertTo-Json -Compress -Depth 10
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

function Assert-Equal {
    param(
        [string]$Step,
        [object]$Actual,
        [object]$Expected
    )
    if ([string]$Actual -eq [string]$Expected) {
        return
    }
    throw ("[{0}] expected {1}, got {2}" -f $Step, $Expected, $Actual)
}

$coreAdminBase = if ($env:CORE_ADMIN_BASE) { $env:CORE_ADMIN_BASE } else { "http://localhost:8001/api/core/v1/admin" }
$tokenCommand = Join-Path $script:RepoRoot "scripts\get_admin_token.cmd"

try {
    Write-Step "===== Finance negative scenarios smoke ====="

    Write-Step "[1/7] Fetch admin token"
    $adminToken = (& cmd /c $tokenCommand).Trim()
    if (-not $adminToken) {
        throw "admin token not resolved"
    }

    $runId = (Get-Date -Format "yyyyMMddHHmmss")
    $clientId = "00000000-0000-0000-0000-00000000f001"
    $invoiceKey = "finance-negative-invoice-$runId"
    $paymentKey1 = "finance-negative-partial-$runId"
    $paymentKey2 = "finance-negative-final-$runId"

    Write-Step "[2/7] Issue invoice"
    $issue = Invoke-Api -Method POST -Url ($coreAdminBase + "/billing/flows/invoices") -OutName "invoice_issue.json" -Token $adminToken -Body @{
        client_id = $clientId
        currency = "RUB"
        amount_total = 1000
        idempotency_key = $invoiceKey
    }
    Assert-Status -Step "issue_invoice" -Actual $issue.StatusCode -Expected @(201)
    $invoiceId = [string]$issue.Json.id
    if (-not $invoiceId) {
        throw "issued invoice id missing"
    }
    Assert-Equal -Step "issue_invoice.status" -Actual $issue.Json.status -Expected "ISSUED"

    Write-Step "[3/7] Capture partial payment"
    $partial = Invoke-Api -Method POST -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/capture") -OutName "payment_partial.json" -Token $adminToken -Body @{
        provider = "MANUAL_SMOKE"
        provider_payment_id = "partial-$runId"
        amount = 400
        currency = "RUB"
        idempotency_key = $paymentKey1
    }
    Assert-Status -Step "partial_payment" -Actual $partial.StatusCode -Expected @(201)
    $partialPaymentId = [string]$partial.Json.id

    $afterPartial = Invoke-Api -Method GET -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId") -OutName "invoice_after_partial.json" -Token $adminToken
    Assert-Status -Step "invoice_after_partial" -Actual $afterPartial.StatusCode -Expected @(200)
    Assert-Equal -Step "invoice_after_partial.status" -Actual $afterPartial.Json.status -Expected "PARTIALLY_PAID"
    Assert-Equal -Step "invoice_after_partial.amount_paid" -Actual $afterPartial.Json.amount_paid -Expected "400.0000"

    Write-Step "[4/7] Replay partial payment idempotently"
    $partialReplay = Invoke-Api -Method POST -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/capture") -OutName "payment_partial_replay.json" -Token $adminToken -Body @{
        provider = "MANUAL_SMOKE"
        provider_payment_id = "partial-replay-$runId"
        amount = 400
        currency = "RUB"
        idempotency_key = $paymentKey1
    }
    Assert-Status -Step "partial_payment_replay" -Actual $partialReplay.StatusCode -Expected @(201)
    Assert-Equal -Step "partial_payment_replay.id" -Actual $partialReplay.Json.id -Expected $partialPaymentId

    $paymentsAfterReplay = Invoke-Api -Method GET -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/payments") -OutName "payments_after_replay.json" -Token $adminToken
    Assert-Status -Step "payments_after_replay" -Actual $paymentsAfterReplay.StatusCode -Expected @(200)
    Assert-Equal -Step "payments_after_replay.total" -Actual $paymentsAfterReplay.Json.total -Expected "1"

    Write-Step "[5/7] Reject idempotency conflict"
    $conflict = Invoke-Api -Method POST -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/capture") -OutName "payment_conflict.json" -Token $adminToken -Body @{
        provider = "MANUAL_SMOKE"
        provider_payment_id = "partial-conflict-$runId"
        amount = 401
        currency = "RUB"
        idempotency_key = $paymentKey1
    }
    Assert-Status -Step "payment_conflict" -Actual $conflict.StatusCode -Expected @(400)
    $paymentsAfterConflict = Invoke-Api -Method GET -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/payments") -OutName "payments_after_conflict.json" -Token $adminToken
    Assert-Status -Step "payments_after_conflict" -Actual $paymentsAfterConflict.StatusCode -Expected @(200)
    Assert-Equal -Step "payments_after_conflict.total" -Actual $paymentsAfterConflict.Json.total -Expected "1"

    Write-Step "[6/7] Capture final payment"
    $final = Invoke-Api -Method POST -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/capture") -OutName "payment_final.json" -Token $adminToken -Body @{
        provider = "MANUAL_SMOKE"
        provider_payment_id = "final-$runId"
        amount = 600
        currency = "RUB"
        idempotency_key = $paymentKey2
    }
    Assert-Status -Step "final_payment" -Actual $final.StatusCode -Expected @(201)

    Write-Step "[7/7] Verify final invoice and payments"
    $afterFinal = Invoke-Api -Method GET -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId") -OutName "invoice_after_final.json" -Token $adminToken
    Assert-Status -Step "invoice_after_final" -Actual $afterFinal.StatusCode -Expected @(200)
    Assert-Equal -Step "invoice_after_final.status" -Actual $afterFinal.Json.status -Expected "PAID"
    Assert-Equal -Step "invoice_after_final.amount_paid" -Actual $afterFinal.Json.amount_paid -Expected "1000.0000"

    $paymentsAfterFinal = Invoke-Api -Method GET -Url ($coreAdminBase + "/billing/flows/invoices/$invoiceId/payments") -OutName "payments_after_final.json" -Token $adminToken
    Assert-Status -Step "payments_after_final" -Actual $paymentsAfterFinal.StatusCode -Expected @(200)
    Assert-Equal -Step "payments_after_final.total" -Actual $paymentsAfterFinal.Json.total -Expected "2"

    Write-Step "FINANCE_NEGATIVE_SCENARIOS: PASS"
    exit 0
} catch {
    Write-Host ("FINANCE_NEGATIVE_SCENARIOS: FAIL - " + $_.Exception.Message)
    exit 1
}
