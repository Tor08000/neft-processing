[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("stage", "prod")]
    [string]$Environment,

    [int]$WindowDays = 0,
    [string]$KubeconfigPath = "",
    [string]$Context = "",
    [string]$Namespace = "",
    [string]$PrometheusUrl = "",
    [string]$LokiUrl = "",
    [string]$GatewayLogPath = "",
    [string]$CoreLogPath = "",
    [string]$CoreLokiSelector = "",
    [string]$GatewayLokiSelector = "",
    [int]$LokiLimit = 5000,
    [string]$OutDir = ".ops/snapshots",
    [switch]$PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-DefaultWindowDays {
    param([string]$EnvName)
    if ($EnvName -eq "stage") {
        return 7
    }
    return 3
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Value
    )
    $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Resolve-ConfigValue {
    param(
        [string]$Explicit,
        [string]$EnvName
    )
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        return $Explicit
    }
    return [Environment]::GetEnvironmentVariable($EnvName)
}

function Resolve-EnvironmentScopedValue {
    param(
        [string]$Explicit,
        [string]$StageEnvName,
        [string]$ProdEnvName,
        [string]$EnvName
    )
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        return $Explicit
    }
    if ($EnvName -eq "stage") {
        return [Environment]::GetEnvironmentVariable($StageEnvName)
    }
    return [Environment]::GetEnvironmentVariable($ProdEnvName)
}

function Normalize-BaseUrl {
    param([string]$Url)
    if ([string]::IsNullOrWhiteSpace($Url)) {
        return ""
    }
    return $Url.TrimEnd("/")
}

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ($listener.LocalEndpoint).Port
    $listener.Stop()
    return $port
}

function Invoke-JsonRequest {
    param([string]$Url)
    return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 20
}

function Resolve-KubeServiceName {
    param(
        [string]$Kubeconfig,
        [string]$KubeContext,
        [string]$KubeNamespace,
        [string]$NameRegex
    )

    $servicesJson = & kubectl --kubeconfig $Kubeconfig --context $KubeContext -n $KubeNamespace get svc -o json
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl get svc failed for namespace '$KubeNamespace'"
    }

    $services = ($servicesJson | ConvertFrom-Json).items
    $candidates = @($services | Where-Object { $_.metadata.name -match $NameRegex } | ForEach-Object { $_.metadata.name })
    if ($candidates.Count -eq 0) {
        throw "No service matched regex '$NameRegex' in namespace '$KubeNamespace'"
    }
    if ($candidates.Count -gt 1) {
        throw "Multiple services matched regex '$NameRegex': $($candidates -join ', ')"
    }
    return $candidates[0]
}

function Start-KubePortForward {
    param(
        [string]$Kubeconfig,
        [string]$KubeContext,
        [string]$KubeNamespace,
        [string]$ServiceName,
        [int]$RemotePort,
        [string]$ProbePath,
        [string]$SnapshotDir
    )

    $localPort = Get-FreeTcpPort
    $stdoutPath = Join-Path $SnapshotDir ("port-forward-" + $ServiceName + "-" + $localPort + ".out.log")
    $stderrPath = Join-Path $SnapshotDir ("port-forward-" + $ServiceName + "-" + $localPort + ".err.log")
    $args = @(
        "--kubeconfig", $Kubeconfig,
        "--context", $KubeContext,
        "-n", $KubeNamespace,
        "port-forward",
        ("svc/" + $ServiceName),
        ("{0}:{1}" -f $localPort, $RemotePort)
    )

    $process = Start-Process -FilePath "kubectl" -ArgumentList $args -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $baseUrl = "http://127.0.0.1:$localPort"
    $probeUrl = $baseUrl + $ProbePath

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $probeUrl -TimeoutSec 2 | Out-Null
            return [pscustomobject]@{
                Process = $process
                BaseUrl = $baseUrl
                StdoutPath = $stdoutPath
                StderrPath = $stderrPath
            }
        } catch {
            if ($process.HasExited) {
                break
            }
        }
    }

    try {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    } catch {
    }
    throw "Failed to establish port-forward for service '$ServiceName'"
}

function Stop-KubePortForward {
    param([object]$ForwardState)
    if ($null -eq $ForwardState) {
        return
    }
    try {
        if (-not $ForwardState.Process.HasExited) {
            Stop-Process -Id $ForwardState.Process.Id -Force
        }
    } catch {
    }
}

function Invoke-PrometheusCompatQuery {
    param(
        [string]$BaseUrl,
        [string]$WindowLiteral
    )

    $query = "sum by (route, method, outcome) (increase(core_api_reports_compat_requests_total[$WindowLiteral]))"
    $uri = "{0}/api/v1/query?query={1}" -f $BaseUrl, [uri]::EscapeDataString($query)
    return Invoke-JsonRequest -Url $uri
}

function Invoke-LokiQueryRange {
    param(
        [string]$BaseUrl,
        [string]$LogQl,
        [datetime]$StartUtc,
        [datetime]$EndUtc,
        [int]$Limit
    )

    $startNs = ([DateTimeOffset]$StartUtc).ToUnixTimeMilliseconds() * 1000000
    $endNs = ([DateTimeOffset]$EndUtc).ToUnixTimeMilliseconds() * 1000000
    $uri = "{0}/loki/api/v1/query_range?query={1}&start={2}&end={3}&limit={4}&direction=forward" -f `
        $BaseUrl, `
        [uri]::EscapeDataString($LogQl), `
        $startNs, `
        $endNs, `
        $Limit
    return Invoke-JsonRequest -Url $uri
}

function Try-ParseJsonLine {
    param([string]$Line)
    if ([string]::IsNullOrWhiteSpace($Line)) {
        return $null
    }
    try {
        return $Line | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Convert-LokiResponseToRecords {
    param(
        [object]$Response,
        [string]$Source,
        [string]$MatchedSignal
    )

    $records = @()
    if ($null -eq $Response.data -or $null -eq $Response.data.result) {
        return $records
    }

    foreach ($stream in $Response.data.result) {
        foreach ($valuePair in $stream.values) {
            $timestampNs = [double]$valuePair[0]
            $line = [string]$valuePair[1]
            $parsed = Try-ParseJsonLine -Line $line
            $record = [ordered]@{
                source = $Source
                matched_signal = $MatchedSignal
                timestamp = ([DateTimeOffset]::FromUnixTimeMilliseconds([int64]($timestampNs / 1000000))).UtcDateTime.ToString("o")
                raw_line = $line
            }

            if ($null -ne $parsed) {
                foreach ($prop in $parsed.PSObject.Properties) {
                    $record[$prop.Name] = $prop.Value
                }
            }

            foreach ($label in $stream.stream.PSObject.Properties) {
                $record["label_" + $label.Name] = $label.Value
            }

            $records += [pscustomobject]$record
        }
    }
    return $records
}

function Convert-GatewayFileToRecords {
    param(
        [string]$Path,
        [object[]]$RouteSpecs
    )

    $records = @()
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $parsed = Try-ParseJsonLine -Line $line
        if ($null -eq $parsed) {
            continue
        }
        $routeSpec = $RouteSpecs | Where-Object { $parsed.uri -like ($_.GatewayMatch + "*") } | Select-Object -First 1
        if ($null -eq $routeSpec) {
            continue
        }
        $records += [pscustomobject]@{
            source = "gateway_file"
            matched_signal = $routeSpec.Route
            request_id = $parsed.request_id
            timestamp = $parsed.time
            route = $routeSpec.Route
            method = $parsed.method
            status = $parsed.status
            user_agent = $parsed.user_agent
            ip = $parsed.remote_addr
            raw_line = $line
        }
    }
    return $records
}

function Convert-CoreFileToRecords {
    param(
        [string]$Path,
        [object[]]$RouteSpecs
    )

    $records = @()
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $parsed = Try-ParseJsonLine -Line $line
        if ($null -eq $parsed) {
            continue
        }
        $routeSpec = $RouteSpecs | Where-Object { $_.CoreEvent -eq $parsed.event_type -or $_.CoreEvent -eq $parsed.message } | Select-Object -First 1
        if ($null -eq $routeSpec -and $parsed.route) {
            $routeSpec = $RouteSpecs | Where-Object { $_.Route -eq $parsed.route } | Select-Object -First 1
        }
        if ($null -eq $routeSpec) {
            continue
        }
        $requestCtx = $parsed.request_ctx
        $records += [pscustomobject]@{
            source = "core_file"
            matched_signal = $routeSpec.CoreEvent
            request_id = if ($requestCtx) { $requestCtx.request_id } else { $null }
            timestamp = if ($parsed.timestamp) { $parsed.timestamp } elseif ($parsed.time) { $parsed.time } else { $null }
            route = if ($parsed.route) { $parsed.route } else { $routeSpec.Route }
            method = $parsed.method
            status = $parsed.status
            user_agent = if ($requestCtx) { $requestCtx.user_agent } else { $null }
            ip = if ($requestCtx) { $requestCtx.ip } else { $null }
            actor_type = if ($requestCtx) { $requestCtx.actor_type } else { $null }
            raw_line = $line
        }
    }
    return $records
}

function Merge-Records {
    param([object[]]$Records)

    $merged = @{}
    $sequence = 0

    foreach ($record in $Records) {
        $sequence += 1
        $key = if (-not [string]::IsNullOrWhiteSpace([string]$record.request_id)) {
            [string]$record.request_id
        } else {
            "{0}:{1}:{2}:{3}" -f $record.source, $record.route, $record.timestamp, $sequence
        }

        if (-not $merged.ContainsKey($key)) {
            $merged[$key] = [ordered]@{
                request_id = $record.request_id
                route = $record.route
                method = $record.method
                timestamp = $record.timestamp
                status = $record.status
                user_agent = $record.user_agent
                ip = $record.ip
                actor_type = $record.actor_type
                matched_signals = @($record.matched_signal)
                sources = @($record.source)
            }
            continue
        }

        $current = $merged[$key]
        foreach ($field in @("route", "method", "timestamp", "status", "user_agent", "ip", "actor_type")) {
            if ([string]::IsNullOrWhiteSpace([string]$current[$field]) -and -not [string]::IsNullOrWhiteSpace([string]$record.$field)) {
                $current[$field] = $record.$field
            }
        }
        if ($record.matched_signal -and -not ($current.matched_signals -contains $record.matched_signal)) {
            $current.matched_signals += $record.matched_signal
        }
        if ($record.source -and -not ($current.sources -contains $record.source)) {
            $current.sources += $record.source
        }
    }

    return @($merged.Values | ForEach-Object { [pscustomobject]$_ })
}

function Get-TrafficClassification {
    param([object]$Record)

    $userAgent = ([string]$Record.user_agent).ToLowerInvariant()
    $actorType = ([string]$Record.actor_type).ToLowerInvariant()
    $route = [string]$Record.route
    $ip = [string]$Record.ip

    $syntheticMarkers = @(
        "kube-probe",
        "prometheus",
        "blackbox",
        "curl",
        "wget",
        "python-requests",
        "httpx",
        "pytest",
        "schemathesis",
        "postmanruntime",
        "insomnia",
        "grafana-agent",
        "healthcheck",
        "readiness",
        "liveness"
    )

    foreach ($marker in $syntheticMarkers) {
        if ($userAgent -like ("*" + $marker + "*")) {
            return [pscustomobject]@{ classification = "synthetic"; reason = "user_agent:" + $marker }
        }
    }

    if ($ip -eq "127.0.0.1" -or $ip -eq "::1") {
        return [pscustomobject]@{ classification = "synthetic"; reason = "loopback_ip" }
    }

    if ($route -eq "/api/v1/reports/billing/summary/rebuild") {
        return [pscustomobject]@{ classification = "internal_admin"; reason = "admin_gated_rebuild_route" }
    }

    if ($actorType -in @("admin", "employee", "ops", "service")) {
        return [pscustomobject]@{ classification = "internal_admin"; reason = "actor_type:" + $actorType }
    }

    return [pscustomobject]@{ classification = "external"; reason = "default_public_read_route" }
}

function Build-MarkdownSummary {
    param(
        [string]$EnvironmentName,
        [string]$WindowLiteral,
        [object]$MetricsResponse,
        [object[]]$MergedRecords,
        [string]$DecisionHint,
        [string]$AccessMode
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Reports compatibility routes usage snapshot")
    $lines.Add("")
    $lines.Add("- Environment: {0}" -f $EnvironmentName)
    $lines.Add("- Window: {0}" -f $WindowLiteral)
    $lines.Add("- Access mode: {0}" -f $AccessMode)
    $lines.Add("- Decision hint: {0}" -f $DecisionHint)
    $lines.Add("")
    $lines.Add("## Metrics")
    $lines.Add("")
    $lines.Add("| route | method | outcome | count |")
    $lines.Add("| --- | --- | --- | ---: |")

    if ($MetricsResponse -and $MetricsResponse.data -and $MetricsResponse.data.result) {
        foreach ($item in $MetricsResponse.data.result | Sort-Object { $_.metric.route }, { $_.metric.outcome }) {
            $lines.Add("| {0} | {1} | {2} | {3} |" -f $item.metric.route, $item.metric.method, $item.metric.outcome, $item.value[1])
        }
    } else {
        $lines.Add("| no_data |  |  | 0 |")
    }

    $lines.Add("")
    $lines.Add("## Classification")
    $lines.Add("")
    $lines.Add("| route | classification | count |")
    $lines.Add("| --- | --- | ---: |")

    $classRows = @(
        $MergedRecords |
            Group-Object route, classification |
            Sort-Object Name |
            ForEach-Object {
                $first = $_.Group | Select-Object -First 1
                [pscustomobject]@{
                    route = $first.route
                    classification = $first.classification
                    count = $_.Count
                }
            }
    )

    if ($classRows.Count -eq 0) {
        $lines.Add("| no_logs |  | 0 |")
    } else {
        foreach ($row in $classRows) {
            $lines.Add("| {0} | {1} | {2} |" -f $row.route, $row.classification, $row.count)
        }
    }

    $lines.Add("")
    $lines.Add("## Samples")
    $lines.Add("")
    foreach ($sample in $MergedRecords | Select-Object -First 10) {
        $lines.Add("- {0} {1} {2} {3} reason={4}" -f $sample.timestamp, $sample.route, $sample.method, $sample.classification, $sample.classification_reason)
    }

    return $lines -join [Environment]::NewLine
}

$routeSpecs = @(
    [pscustomobject]@{ Route = "/api/v1/reports/billing/daily"; Method = "GET"; CoreEvent = "reports_billing_daily_read"; GatewayMatch = "/api/v1/reports/billing/daily" },
    [pscustomobject]@{ Route = "/api/v1/reports/billing/summary"; Method = "GET"; CoreEvent = "reports_billing_summary_read"; GatewayMatch = "/api/v1/reports/billing/summary" },
    [pscustomobject]@{ Route = "/api/v1/reports/turnover"; Method = "GET"; CoreEvent = "reports_turnover_read"; GatewayMatch = "/api/v1/reports/turnover" },
    [pscustomobject]@{ Route = "/api/v1/reports/turnover/export"; Method = "GET"; CoreEvent = "reports_turnover_export"; GatewayMatch = "/api/v1/reports/turnover/export" },
    [pscustomobject]@{ Route = "/api/v1/reports/billing/summary/rebuild"; Method = "POST"; CoreEvent = "reports_billing_summary_rebuild"; GatewayMatch = "/api/v1/reports/billing/summary/rebuild" }
)

if ($WindowDays -le 0) {
    $WindowDays = Get-DefaultWindowDays -EnvName $Environment
}

$KubeconfigPath = Resolve-ConfigValue -Explicit $KubeconfigPath -EnvName "NEFT_OBS_KUBECONFIG"
$Context = Resolve-EnvironmentScopedValue -Explicit $Context -StageEnvName "NEFT_STAGE_CONTEXT" -ProdEnvName "NEFT_PROD_CONTEXT" -EnvName $Environment
$Namespace = Resolve-EnvironmentScopedValue -Explicit $Namespace -StageEnvName "NEFT_STAGE_NAMESPACE" -ProdEnvName "NEFT_PROD_NAMESPACE" -EnvName $Environment
$PrometheusUrl = Normalize-BaseUrl -Url (Resolve-ConfigValue -Explicit $PrometheusUrl -EnvName "NEFT_OBS_PROMETHEUS_URL")
$LokiUrl = Normalize-BaseUrl -Url (Resolve-ConfigValue -Explicit $LokiUrl -EnvName "NEFT_OBS_LOKI_URL")
$CoreLokiSelector = Resolve-ConfigValue -Explicit $CoreLokiSelector -EnvName "NEFT_OBS_CORE_LOKI_SELECTOR"
$GatewayLokiSelector = Resolve-ConfigValue -Explicit $GatewayLokiSelector -EnvName "NEFT_OBS_GATEWAY_LOKI_SELECTOR"

if ([string]::IsNullOrWhiteSpace($CoreLokiSelector)) {
    $CoreLokiSelector = '{service="core-api"}'
}
if ([string]::IsNullOrWhiteSpace($GatewayLokiSelector)) {
    $GatewayLokiSelector = '{service="gateway"}'
}

$windowLiteral = "{0}d" -f $WindowDays
$startUtc = (Get-Date).ToUniversalTime().AddDays(-$WindowDays)
$endUtc = (Get-Date).ToUniversalTime()
$timestampLabel = $endUtc.ToString("yyyyMMdd-HHmmssZ")
$snapshotDir = Join-Path (Resolve-Path ".").Path (Join-Path $OutDir (Join-Path $Environment $timestampLabel))
Ensure-Directory -Path $snapshotDir

$plan = [pscustomobject]@{
    environment = $Environment
    window_days = $WindowDays
    window_literal = $windowLiteral
    kubeconfig_path = $KubeconfigPath
    context = $Context
    namespace = $Namespace
    prometheus_url = $PrometheusUrl
    loki_url = $LokiUrl
    gateway_log_path = $GatewayLogPath
    core_log_path = $CoreLogPath
    snapshot_dir = $snapshotDir
    core_loki_selector = $CoreLokiSelector
    gateway_loki_selector = $GatewayLokiSelector
}
Write-JsonFile -Path (Join-Path $snapshotDir "plan.json") -Value $plan

if ($PlanOnly) {
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

$portForwards = @()
$accessMode = "direct"

try {
    if ([string]::IsNullOrWhiteSpace($PrometheusUrl) -or [string]::IsNullOrWhiteSpace($LokiUrl)) {
        if ([string]::IsNullOrWhiteSpace($KubeconfigPath) -or [string]::IsNullOrWhiteSpace($Context) -or [string]::IsNullOrWhiteSpace($Namespace)) {
            throw "Need either direct Prometheus/Loki URLs or kubeconfig + context + namespace."
        }
        if (-not (Test-Path -LiteralPath $KubeconfigPath)) {
            throw "Kubeconfig not found: $KubeconfigPath"
        }

        $accessMode = "kube_port_forward"
        $prometheusService = Resolve-KubeServiceName -Kubeconfig $KubeconfigPath -KubeContext $Context -KubeNamespace $Namespace -NameRegex "prometheus"
        $lokiService = Resolve-KubeServiceName -Kubeconfig $KubeconfigPath -KubeContext $Context -KubeNamespace $Namespace -NameRegex "loki"

        $promForward = Start-KubePortForward -Kubeconfig $KubeconfigPath -KubeContext $Context -KubeNamespace $Namespace -ServiceName $prometheusService -RemotePort 9090 -ProbePath "/-/ready" -SnapshotDir $snapshotDir
        $lokiForward = Start-KubePortForward -Kubeconfig $KubeconfigPath -KubeContext $Context -KubeNamespace $Namespace -ServiceName $lokiService -RemotePort 3100 -ProbePath "/ready" -SnapshotDir $snapshotDir
        $portForwards += $promForward
        $portForwards += $lokiForward
        $PrometheusUrl = $promForward.BaseUrl
        $LokiUrl = $lokiForward.BaseUrl
    }

    $metricsResponse = Invoke-PrometheusCompatQuery -BaseUrl $PrometheusUrl -WindowLiteral $windowLiteral
    Write-JsonFile -Path (Join-Path $snapshotDir "prometheus_metrics.json") -Value $metricsResponse

    $rawRecords = @()
    foreach ($spec in $routeSpecs) {
        $coreQuery = $CoreLokiSelector + ' |= "' + $spec.CoreEvent + '"'
        $gatewayQuery = $GatewayLokiSelector + ' |= "' + $spec.GatewayMatch + '"'

        if (-not [string]::IsNullOrWhiteSpace($LokiUrl)) {
            $coreResponse = Invoke-LokiQueryRange -BaseUrl $LokiUrl -LogQl $coreQuery -StartUtc $startUtc -EndUtc $endUtc -Limit $LokiLimit
            $gatewayResponse = Invoke-LokiQueryRange -BaseUrl $LokiUrl -LogQl $gatewayQuery -StartUtc $startUtc -EndUtc $endUtc -Limit $LokiLimit
            Write-JsonFile -Path (Join-Path $snapshotDir ((($spec.CoreEvent) + ".core.loki.json"))) -Value $coreResponse
            Write-JsonFile -Path (Join-Path $snapshotDir ((($spec.Route -replace '[/:]', '_') + ".gateway.loki.json"))) -Value $gatewayResponse
            $rawRecords += Convert-LokiResponseToRecords -Response $coreResponse -Source "core_loki" -MatchedSignal $spec.CoreEvent
            $rawRecords += Convert-LokiResponseToRecords -Response $gatewayResponse -Source "gateway_loki" -MatchedSignal $spec.Route
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($GatewayLogPath)) {
        if (-not (Test-Path -LiteralPath $GatewayLogPath)) {
            throw "Gateway log file not found: $GatewayLogPath"
        }
        $rawRecords += Convert-GatewayFileToRecords -Path $GatewayLogPath -RouteSpecs $routeSpecs
    }

    if (-not [string]::IsNullOrWhiteSpace($CoreLogPath)) {
        if (-not (Test-Path -LiteralPath $CoreLogPath)) {
            throw "Core log file not found: $CoreLogPath"
        }
        $rawRecords += Convert-CoreFileToRecords -Path $CoreLogPath -RouteSpecs $routeSpecs
    }

    $mergedRecords = Merge-Records -Records $rawRecords
    foreach ($record in $mergedRecords) {
        $classification = Get-TrafficClassification -Record $record
        Add-Member -InputObject $record -MemberType NoteProperty -Name classification -Value $classification.classification
        Add-Member -InputObject $record -MemberType NoteProperty -Name classification_reason -Value $classification.reason
    }

    Write-JsonFile -Path (Join-Path $snapshotDir "merged_route_records.json") -Value $mergedRecords

    $externalCount = @($mergedRecords | Where-Object { $_.classification -eq "external" }).Count
    $decisionHint = if ($externalCount -gt 0) {
        "guarded_handoff_plan"
    } else {
        "final_compatibility_freeze"
    }

    $summary = [pscustomobject]@{
        environment = $Environment
        window_literal = $windowLiteral
        access_mode = $accessMode
        decision_hint = $decisionHint
        external_count = $externalCount
        synthetic_count = @($mergedRecords | Where-Object { $_.classification -eq "synthetic" }).Count
        internal_admin_count = @($mergedRecords | Where-Object { $_.classification -eq "internal_admin" }).Count
        metrics_result_count = if ($metricsResponse.data -and $metricsResponse.data.result) { @($metricsResponse.data.result).Count } else { 0 }
    }
    Write-JsonFile -Path (Join-Path $snapshotDir "summary.json") -Value $summary
    $markdown = Build-MarkdownSummary -EnvironmentName $Environment -WindowLiteral $windowLiteral -MetricsResponse $metricsResponse -MergedRecords $mergedRecords -DecisionHint $decisionHint -AccessMode $accessMode
    Set-Content -LiteralPath (Join-Path $snapshotDir "summary.md") -Value $markdown -Encoding UTF8

    $summary | ConvertTo-Json -Depth 5
} finally {
    foreach ($forward in $portForwards) {
        Stop-KubePortForward -ForwardState $forward
    }
}
