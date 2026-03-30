$ErrorActionPreference = 'Stop'

$containerName = if ($env:SIGNAL_FLOW_PG_CONTAINER_NAME) { $env:SIGNAL_FLOW_PG_CONTAINER_NAME } else { 'signal-flow-postgres' }
$postgresUser = if ($env:SIGNAL_FLOW_PG_USER) { $env:SIGNAL_FLOW_PG_USER } else { 'signalflow' }
$postgresPassword = if ($env:SIGNAL_FLOW_PG_PASSWORD) { $env:SIGNAL_FLOW_PG_PASSWORD } else { 'signalflow' }
$postgresDb = if ($env:SIGNAL_FLOW_PG_DB) { $env:SIGNAL_FLOW_PG_DB } else { 'signal_flow' }
$hostPort = if ($env:SIGNAL_FLOW_PG_PORT) { $env:SIGNAL_FLOW_PG_PORT } else { '5432' }

$existing = docker ps -a --filter "name=^/${containerName}$" --format "{{.Names}}"
if ($existing -eq $containerName) {
    docker start $containerName | Out-Null
} else {
    docker run -d `
        --name $containerName `
        -e POSTGRES_USER=$postgresUser `
        -e POSTGRES_PASSWORD=$postgresPassword `
        -e POSTGRES_DB=$postgresDb `
        -p "${hostPort}:5432" `
        postgres:16 | Out-Null
}

Write-Output "DATABASE_URL=postgresql+psycopg://${postgresUser}:${postgresPassword}@127.0.0.1:${hostPort}/${postgresDb}"
