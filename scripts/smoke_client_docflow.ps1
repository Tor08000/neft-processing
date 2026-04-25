$ErrorActionPreference = "Stop"

$script:ScriptName = "smoke_client_docflow"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:RunTs = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogDir = Join-Path $script:RepoRoot "logs"
$localTemp = if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    Join-Path $env:LOCALAPPDATA "Temp"
} else {
    [System.IO.Path]::GetTempPath().TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}
if (-not [System.IO.Directory]::Exists($localTemp)) {
    $localTemp = [System.IO.Path]::GetTempPath().TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}
$script:TempDir = Join-Path $localTemp ($script:ScriptName + "_" + $script:RunTs)
$script:LogFile = Join-Path $script:LogDir ($script:ScriptName + "_" + $script:RunTs + ".log")

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
        Content = $content
        Json = $json
        Path = $path
    }
}

function Invoke-JsonStep {
    param(
        [string]$Step,
        [ValidateSet("GET", "POST", "PUT")]
        [string]$Method,
        [string]$Url,
        [int[]]$Expected,
        [string]$OutName,
        [string]$Token = "",
        [object]$Body = $null
    )
    Write-Log ("[{0}] {1} {2}" -f $Step, $Method, $Url)
    $response = Invoke-Api -Method $Method -Url $Url -OutName $OutName -Token $Token -Body $Body
    Write-Log ("Status: " + $response.StatusCode)
    if ($Expected -notcontains $response.StatusCode) {
        throw ("[{0}] expected HTTP {1}, got {2}" -f $Step, ($Expected -join ","), $response.StatusCode)
    }
    if ($null -eq $response.Json) {
        throw ("[{0}] response must be JSON" -f $Step)
    }
    return $response
}

function Invoke-UploadDocument {
    param(
        [string]$Step,
        [string]$Url,
        [string]$Token,
        [string]$DocType,
        [string]$FilePath,
        [string]$OutName
    )
    $outPath = Join-Path $script:TempDir $OutName
    Write-Log ("[{0}] POST {1} ({2})" -f $Step, $Url, $DocType)
    $code = & curl.exe -sS -o "$outPath" -w "%{http_code}" -X POST `
        "$Url" `
        -H "Authorization: Bearer $Token" `
        -F "doc_type=$DocType" `
        -F "file=@$FilePath;type=application/pdf"
    $content = if (Test-Path $outPath) { Get-Content -Raw -Path $outPath } else { "" }
    Save-Response -Name $OutName -Content $content | Out-Null
    Write-Log ("Status: " + $code)
    if ($code -ne "201") {
        throw ("[{0}] expected HTTP 201, got {1}" -f $Step, $code)
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

function Get-EnvOrDefault {
    param(
        [string]$Name,
        [string]$Default
    )
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

$baseUrl = (Get-EnvOrDefault -Name "BASE_URL" -Default "http://localhost").TrimEnd("/")
$authUrl = (Get-EnvOrDefault -Name "AUTH_URL" -Default ($baseUrl + "/api/v1/auth")).TrimEnd("/")
$coreUrl = (Get-EnvOrDefault -Name "CORE_URL" -Default ($baseUrl + "/api/core")).TrimEnd("/")
$onboardingBase = $coreUrl + "/client/v1/onboarding"
$docflowBase = $coreUrl + "/client/docflow"
$adminReviewBase = $coreUrl + "/admin/v1/onboarding"
$adminEmail = Get-EnvOrDefault -Name "ADMIN_EMAIL" -Default "admin@neft.local"
$adminPassword = Get-EnvOrDefault -Name "ADMIN_PASSWORD" -Default "Neft123!"

$samplePdf = Join-Path $script:TempDir "sample.pdf"
[System.IO.File]::WriteAllText($samplePdf, "%PDF-1.7 smoke docflow", [System.Text.UTF8Encoding]::new($false))

$exitCode = 0
try {
    Write-Log ("Starting {0}" -f $script:ScriptName)
    Write-Log ("AUTH_URL={0}" -f $authUrl)
    Write-Log ("CORE_URL={0}" -f $coreUrl)

    $email = "smoke-docflow-{0}@example.com" -f ([Guid]::NewGuid().ToString("N").Substring(0, 12))
    $create = Invoke-JsonStep -Step "1_create_application" -Method POST -Url ($onboardingBase + "/applications") -Expected @(200) -OutName "create.json" -Body @{
        email = $email
    }
    $appId = [string]$create.Json.application.id
    $onboardingToken = [string]$create.Json.access_token
    Assert-True -Step "1_create_application" -Condition (-not [string]::IsNullOrWhiteSpace($appId)) -Message "missing application id"
    Assert-True -Step "1_create_application" -Condition (-not [string]::IsNullOrWhiteSpace($onboardingToken)) -Message "missing onboarding token"

    Invoke-JsonStep -Step "2_patch_application" -Method PUT -Url ($onboardingBase + "/applications/" + $appId) -Token $onboardingToken -Expected @(200) -OutName "patch.json" -Body @{
        company_name = "Smoke Docflow LLC"
        inn = "7701234567"
        org_type = "LEGAL"
        ogrn = "1234567890123"
    } | Out-Null

    foreach ($docType in @("CHARTER", "EGRUL", "BANK_DETAILS")) {
        Invoke-UploadDocument -Step ("3_upload_" + $docType) -Url ($onboardingBase + "/applications/" + $appId + "/documents") -Token $onboardingToken -DocType $docType -FilePath $samplePdf -OutName ("upload_" + $docType + ".json")
    }

    Invoke-JsonStep -Step "4_submit_application" -Method POST -Url ($onboardingBase + "/applications/" + $appId + "/submit") -Token $onboardingToken -Expected @(200) -OutName "submit.json" | Out-Null

    $adminLogin = Invoke-JsonStep -Step "5_admin_login" -Method POST -Url ($authUrl + "/login") -Expected @(200) -OutName "admin_login.json" -Body @{
        email = $adminEmail
        login = $adminEmail
        password = $adminPassword
        portal = "admin"
    }
    $adminToken = [string]$adminLogin.Json.access_token
    Assert-True -Step "5_admin_login" -Condition (-not [string]::IsNullOrWhiteSpace($adminToken)) -Message "missing admin token"

    Invoke-JsonStep -Step "6_start_review" -Method POST -Url ($adminReviewBase + "/applications/" + $appId + "/start-review") -Token $adminToken -Expected @(200) -OutName "start_review.json" | Out-Null

    Invoke-JsonStep -Step "7_generate_docs" -Method POST -Url ($onboardingBase + "/applications/" + $appId + "/generate-docs") -Token $onboardingToken -Expected @(200) -OutName "generate_docs.json" | Out-Null
    $generatedDocs = Invoke-JsonStep -Step "8_list_generated_docs" -Method GET -Url ($onboardingBase + "/applications/" + $appId + "/generated-docs") -Token $onboardingToken -Expected @(200) -OutName "generated_docs.json"
    $docId = [string]$generatedDocs.Json.items[0].id
    Assert-True -Step "8_list_generated_docs" -Condition (-not [string]::IsNullOrWhiteSpace($docId)) -Message "missing generated doc id"

    $otpStart = Invoke-JsonStep -Step "9_otp_start" -Method POST -Url ($onboardingBase + "/generated-docs/" + $docId + "/sign/otp/start") -Token $onboardingToken -Expected @(200) -OutName "otp_start.json" -Body @{
        channel = "sms"
        destination = "+79990000000"
    }
    $challengeId = [string]$otpStart.Json.challenge_id
    $otpCode = [string]$otpStart.Json.otp_code
    Assert-True -Step "9_otp_start" -Condition (-not [string]::IsNullOrWhiteSpace($challengeId)) -Message "missing challenge id"
    Assert-True -Step "9_otp_start" -Condition (-not [string]::IsNullOrWhiteSpace($otpCode)) -Message "missing echoed OTP code"

    $otpConfirm = Invoke-JsonStep -Step "10_otp_confirm" -Method POST -Url ($onboardingBase + "/generated-docs/" + $docId + "/sign/otp/confirm") -Token $onboardingToken -Expected @(200) -OutName "otp_confirm.json" -Body @{
        challenge_id = $challengeId
        code = $otpCode
    }
    Assert-True -Step "10_otp_confirm" -Condition ([string]$otpConfirm.Json.doc.status -eq "SIGNED_BY_CLIENT") -Message "expected SIGNED_BY_CLIENT"

    $timeline = Invoke-JsonStep -Step "11_timeline" -Method GET -Url ($docflowBase + "/timeline?application_id=" + $appId) -Token $onboardingToken -Expected @(200) -OutName "timeline.json"
    $timelineHit = @($timeline.Json.items | Where-Object {
        [string]$_.event_type -eq "DOC_SIGNED_BY_CLIENT" -and [string]$_.doc_id -eq $docId -and [string]$_.application_id -eq $appId
    }).Count -gt 0
    Assert-True -Step "11_timeline" -Condition $timelineHit -Message "timeline missing DOC_SIGNED_BY_CLIENT event"

    $package = Invoke-JsonStep -Step "12_package_create" -Method POST -Url ($docflowBase + "/packages") -Token $onboardingToken -Expected @(200) -OutName "package_create.json" -Body @{
        application_id = $appId
        doc_ids = @($docId)
    }
    $packageId = [string]$package.Json.id
    Assert-True -Step "12_package_create" -Condition ($package.Json.status -eq "READY") -Message "expected READY package"
    Assert-True -Step "12_package_create" -Condition (-not [string]::IsNullOrWhiteSpace($packageId)) -Message "missing package id"

    $packages = Invoke-JsonStep -Step "13_package_list" -Method GET -Url ($docflowBase + "/packages?application_id=" + $appId) -Token $onboardingToken -Expected @(200) -OutName "packages.json"
    $packageHit = @($packages.Json.items | Where-Object { [string]$_.id -eq $packageId }).Count -gt 0
    Assert-True -Step "13_package_list" -Condition $packageHit -Message "package id not present in package list"

    $downloadFile = Join-Path $script:TempDir "package.zip"
    $downloadUrl = $docflowBase + "/packages/" + $packageId + "/download"
    Write-Log ("[14_package_download] GET {0}" -f $downloadUrl)
    $downloadCode = & curl.exe -sS -L -o "$downloadFile" -w "%{http_code}" `
        -H "Authorization: Bearer $onboardingToken" `
        "$downloadUrl"
    Write-Log ("Status: " + $downloadCode)
    Assert-True -Step "14_package_download" -Condition ($downloadCode -eq "200") -Message "package download failed"
    Assert-True -Step "14_package_download" -Condition ((Test-Path $downloadFile) -and ((Get-Item $downloadFile).Length -gt 0)) -Message "package zip is empty"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($downloadFile)
    try {
        $names = @($zip.Entries | ForEach-Object { $_.FullName })
        Assert-True -Step "14_package_download" -Condition (@($names | Where-Object { $_.StartsWith("outbound/") }).Count -gt 0) -Message "expected outbound payloads"
        Assert-True -Step "14_package_download" -Condition (@($names | Where-Object { $_.StartsWith("signatures/") }).Count -gt 0) -Message "expected signature payloads"
    } finally {
        $zip.Dispose()
    }

    $notifications = Invoke-JsonStep -Step "15_notifications" -Method GET -Url ($docflowBase + "/notifications") -Token $onboardingToken -Expected @(200) -OutName "notifications.json"
    Assert-True -Step "15_notifications" -Condition ([int]$notifications.Json.unread_count -ge 1) -Message "expected unread notifications"
    $notification = @($notifications.Json.items | Where-Object {
        [string]$_.kind -eq "DOC_SIGNED_BY_CLIENT" -and [string]$_.payload.doc_id -eq $docId
    } | Select-Object -First 1)
    Assert-True -Step "15_notifications" -Condition ($notification.Count -gt 0) -Message "expected DOC_SIGNED_BY_CLIENT notification"

    $read = Invoke-JsonStep -Step "16_notification_read" -Method POST -Url ($docflowBase + "/notifications/" + [string]$notification[0].id + "/read") -Token $onboardingToken -Expected @(200) -OutName "notification_read.json"
    Assert-True -Step "16_notification_read" -Condition (-not [string]::IsNullOrWhiteSpace([string]$read.Json.read_at)) -Message "expected read_at after mark read"

    Write-Log "SMOKE_CLIENT_DOCFLOW: PASS"
} catch {
    $exitCode = 1
    Write-Log ("SMOKE_CLIENT_DOCFLOW: FAIL - " + $_.Exception.Message)
} finally {
    try {
        if (-not [string]::IsNullOrWhiteSpace($script:TempDir) -and [System.IO.Directory]::Exists($script:TempDir)) {
            [System.IO.Directory]::Delete($script:TempDir, $true)
        }
    } catch {
        Write-Log ("Temp cleanup skipped: " + $_.Exception.Message)
    }
}

exit $exitCode
