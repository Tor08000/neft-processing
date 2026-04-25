$ErrorActionPreference = "Stop"

$script:Name = "smoke_client_active_e2e"
$script:RepoRoot = Split-Path $PSScriptRoot -Parent
$script:RunTs = Get-Date -Format "yyyyMMdd_HHmmss"
$script:LogDir = Join-Path $script:RepoRoot "logs"
$script:TempDir = Join-Path $env:TEMP ($script:Name + "_" + $script:RunTs)
$script:LogFile = Join-Path $script:LogDir ($script:Name + "_" + $script:RunTs + ".log")

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
        [object]$Body = $null,
        [string]$ContentType = "application/json"
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
            $response = Invoke-WebRequest -Method $Method -Uri $Url -Headers $headers -ContentType $ContentType -Body $bodyJson -UseBasicParsing
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
        Content = $content
        Json = $json
        Path = $path
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

function Invoke-Step {
    param(
        [string]$Step,
        [ValidateSet("GET", "POST")]
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
    Assert-Status -Step $Step -Actual $response.StatusCode -Expected $Expected
    return $response
}

function Assert-PortalState {
    param(
        [string]$Step,
        [string]$Expected,
        [string]$CoreBase,
        [string]$Token,
        [switch]$RequireOrg
    )
    $response = Invoke-Step -Step $Step -Method GET -Url ($CoreBase + "/portal/me") -Expected @(200) -OutName ($Step + "_portal_me.json") -Token $Token
    Assert-True -Step $Step -Condition ($null -ne $response.Json) -Message "portal/me must return JSON"
    $state = [string]$response.Json.access_state
    Write-Log ("[{0}] access_state={1} expected={2}" -f $Step, $state, $Expected)
    Assert-True -Step $Step -Condition ($state -eq $Expected) -Message ("expected access_state " + $Expected + ", got " + $state)
    if ($RequireOrg) {
        $org = $response.Json.org
        $entitlements = $response.Json.entitlements_snapshot
        $roles = @($response.Json.org_roles | ForEach-Object { [string]$_ })
        $userRoles = @($response.Json.user_roles | ForEach-Object { [string]$_ })
        $memberships = @($response.Json.memberships | ForEach-Object { [string]$_ })
        Assert-True -Step $Step -Condition ($response.Json.flags.portal_me_failed -ne $true) -Message "portal_me_failed must not be true"
        Assert-True -Step $Step -Condition ($null -ne $org -and -not [string]::IsNullOrWhiteSpace([string]$org.id)) -Message "org context must be present"
        Assert-True -Step $Step -Condition (-not [string]::IsNullOrWhiteSpace([string]$response.Json.org_status)) -Message "org_status must be present"
        Assert-True -Step $Step -Condition ($null -ne $entitlements -and -not [string]::IsNullOrWhiteSpace([string]$entitlements.org_id)) -Message "entitlements org_id must be present"
        Assert-True -Step $Step -Condition ($roles -contains "CLIENT") -Message "org_roles must include CLIENT"
        Assert-True -Step $Step -Condition ($userRoles -contains "CLIENT_OWNER") -Message "user_roles must include CLIENT_OWNER"
        Assert-True -Step $Step -Condition ($memberships -contains "CLIENT") -Message "memberships must include CLIENT"
    }
    return $response
}

Import-DotEnvDefaults

$gatewayBase = Get-Config -Names @("GATEWAY_BASE", "BASE_URL", "GATEWAY_BASE_URL") -Default "http://localhost"
$authBase = Get-Config -Names @("AUTH_BASE") -Default "/api/v1/auth"
$coreBasePath = Get-Config -Names @("CORE_BASE") -Default "/api/core"
$authUrl = $gatewayBase.TrimEnd("/") + $authBase
$coreUrl = $gatewayBase.TrimEnd("/") + $coreBasePath

$smokeEmail = "client_active_{0}@example.com" -f (Get-Random -Minimum 100000 -Maximum 999999)
$smokePassword = "ClientActive123!"
$otpCode = "0000"
$orgName = "Smoke Client"
$orgInn = "77{0}" -f (Get-Random -Minimum 10000000 -Maximum 99999999)
$orgKpp = "77{0}001" -f (Get-Random -Minimum 1000 -Maximum 9999)
$orgOgrn = "10277{0}" -f (Get-Random -Minimum 10000000 -Maximum 99999999)

$exitCode = 0
try {
    Write-Log ("Starting {0}" -f $script:Name)
    Write-Log ("AUTH_URL={0}" -f $authUrl)
    Write-Log ("CORE_URL={0}" -f $coreUrl)

    $signup = Invoke-Step -Step "1_signup" -Method POST -Url ($authUrl + "/signup") -Expected @(201) -OutName "signup.json" -Body @{
        email = $smokeEmail
        password = $smokePassword
        full_name = "Client Active Smoke"
        consent_personal_data = $true
        consent_offer = $true
    }
    Assert-True -Step "1_signup" -Condition ($null -ne $signup.Json) -Message "signup must return JSON"
    $ownerUserId = [string]$signup.Json.id
    Assert-True -Step "1_signup" -Condition (-not [string]::IsNullOrWhiteSpace($ownerUserId)) -Message "signup response must include owner user id"

    $login = Invoke-Step -Step "2_login" -Method POST -Url ($authUrl + "/login") -Expected @(200) -OutName "login.json" -Body @{
        email = $smokeEmail
        password = $smokePassword
        portal = "client"
    }
    $clientToken = [string]$login.Json.access_token
    Assert-True -Step "2_login" -Condition (-not [string]::IsNullOrWhiteSpace($clientToken)) -Message "login response must include access_token"

    Assert-PortalState -Step "3_needs_onboarding" -Expected "NEEDS_ONBOARDING" -CoreBase $coreUrl -Token $clientToken | Out-Null

    Invoke-Step -Step "4_org_create" -Method POST -Url ($coreUrl + "/client/onboarding/profile") -Expected @(200) -OutName "org_create.json" -Token $clientToken -Body @{
        org_type = "LEGAL"
        name = $orgName
        inn = $orgInn
        kpp = $orgKpp
        ogrn = $orgOgrn
        address = "Moscow"
    } | Out-Null

    Assert-PortalState -Step "5_needs_plan" -Expected "NEEDS_PLAN" -CoreBase $coreUrl -Token $clientToken -RequireOrg | Out-Null

    $plans = Invoke-Step -Step "6_plans" -Method GET -Url ($coreUrl + "/client/plans") -Expected @(200) -OutName "plans.json" -Token $clientToken
    $planItems = @($plans.Json)
    $planCode = [string](($planItems | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.code) } | Select-Object -First 1).code)
    Assert-True -Step "6_plans" -Condition (-not [string]::IsNullOrWhiteSpace($planCode)) -Message "plans response must include a code"

    Invoke-Step -Step "7_plan_select" -Method POST -Url ($coreUrl + "/client/subscription") -Expected @(200) -OutName "plan_select.json" -Token $clientToken -Body @{
        plan_code = $planCode
    } | Out-Null

    Assert-PortalState -Step "8_needs_contract" -Expected "NEEDS_CONTRACT" -CoreBase $coreUrl -Token $clientToken | Out-Null

    $contract = Invoke-Step -Step "9_contract_generate" -Method POST -Url ($coreUrl + "/client/contracts/generate") -Expected @(200) -OutName "contract_generate.json" -Token $clientToken -Body @{}
    $contractId = [string]$contract.Json.contract_id
    Assert-True -Step "9_contract_generate" -Condition (-not [string]::IsNullOrWhiteSpace($contractId)) -Message "contract response must include contract_id"

    Invoke-Step -Step "10_contracts_list" -Method GET -Url ($coreUrl + "/client/contracts") -Expected @(200) -OutName "contracts_list.json" -Token $clientToken | Out-Null
    Invoke-Step -Step "11_contract_get" -Method GET -Url ($coreUrl + "/client/contracts/" + $contractId) -Expected @(200) -OutName "contract_get.json" -Token $clientToken | Out-Null
    Invoke-Step -Step "12_contract_sign" -Method POST -Url ($coreUrl + "/client/contracts/" + $contractId + "/sign") -Expected @(200) -OutName "contract_sign.json" -Token $clientToken -Body @{
        otp = $otpCode
    } | Out-Null

    Assert-PortalState -Step "13_active" -Expected "ACTIVE" -CoreBase $coreUrl -Token $clientToken | Out-Null

    $inviteEmail = "driver_{0}@example.com" -f (Get-Random -Minimum 100000 -Maximum 999999)
    $invite = Invoke-Step -Step "14_user_invite" -Method POST -Url ($coreUrl + "/client/users/invite") -Expected @(201) -OutName "user_invite.json" -Token $clientToken -Body @{
        email = $inviteEmail
        roles = @("CLIENT_VIEWER")
    }
    $invitationId = [string]$invite.Json.invitation_id
    Assert-True -Step "14_user_invite" -Condition (-not [string]::IsNullOrWhiteSpace($invitationId)) -Message "invite response must include invitation_id"
    Assert-True -Step "14_user_invite" -Condition ([string]$invite.Json.status -eq "PENDING") -Message "invite response must be pending"

    $card = Invoke-Step -Step "15_issue_card" -Method POST -Url ($coreUrl + "/client/cards") -Expected @(201) -OutName "card.json" -Token $clientToken -Body @{
        pan_masked = "5555 ****"
    }
    $cardId = [string]$card.Json.id
    Assert-True -Step "15_issue_card" -Condition (-not [string]::IsNullOrWhiteSpace($cardId)) -Message "card response must include id"

    Invoke-Step -Step "16_assign_card" -Method POST -Url ($coreUrl + "/client/cards/" + $cardId + "/access") -Expected @(200) -OutName "card_assign.json" -Token $clientToken -Body @{
        user_id = $ownerUserId
        scope = "VIEW"
    } | Out-Null

    $docs = Invoke-Step -Step "17_docs_contracts" -Method GET -Url ($coreUrl + "/client/docs/contracts") -Expected @(200) -OutName "docs_contracts.json" -Token $clientToken
    $items = @($docs.Json.items)
    $downloadUrl = [string](($items | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.download_url) } | Select-Object -First 1).download_url)
    Assert-True -Step "17_docs_contracts" -Condition (-not [string]::IsNullOrWhiteSpace($downloadUrl)) -Message "contracts list must include download_url"

    Invoke-Step -Step "18_contract_download" -Method GET -Url ($gatewayBase.TrimEnd("/") + $downloadUrl) -Expected @(200) -OutName "contract_download.pdf" -Token $clientToken | Out-Null

    Write-Log "E2E_CLIENT_ACTIVE: PASS"
} catch {
    $exitCode = 1
    Write-Log ("E2E_CLIENT_ACTIVE: FAIL - " + $_.Exception.Message)
}

exit $exitCode
