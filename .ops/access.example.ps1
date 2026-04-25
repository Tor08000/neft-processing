$env:NEFT_OBS_KUBECONFIG = "C:\neft-processing\.ops\kubeconfig.yaml"

$env:NEFT_STAGE_CONTEXT = "stage-context-name"
$env:NEFT_STAGE_NAMESPACE = "neft-stage"

$env:NEFT_PROD_CONTEXT = "prod-context-name"
$env:NEFT_PROD_NAMESPACE = "neft-prod"

# Optional direct endpoints if kube port-forward is not needed.
$env:NEFT_OBS_PROMETHEUS_URL = ""
$env:NEFT_OBS_LOKI_URL = ""

# Optional Loki selectors when cluster labels differ from the local docker defaults.
$env:NEFT_OBS_CORE_LOKI_SELECTOR = "{service=""core-api""}"
$env:NEFT_OBS_GATEWAY_LOKI_SELECTOR = "{service=""gateway""}"
