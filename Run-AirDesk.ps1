param([ValidateSet('Demo','Numerical','Export','Test','Report')][string]$Action = 'Demo')
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create the Python environment using README.md first.' }
Push-Location -LiteralPath $PSScriptRoot
try {
    function Invoke-AirDeskStage {
        param([string[]]$StageArguments)
        & $taskPython -m airdesk @StageArguments
        if ($LASTEXITCODE -ne 0) { throw "AirDesk stage failed: $StageArguments" }
    }
    switch ($Action) {
        'Demo' { Invoke-AirDeskStage -StageArguments @('demo') }
        'Numerical' {
            Invoke-AirDeskStage -StageArguments @('environment')
            Invoke-AirDeskStage -StageArguments @('mechanics')
            Invoke-AirDeskStage -StageArguments @('spice-smoke')
            Invoke-AirDeskStage -StageArguments @('femm','--full')
            Invoke-AirDeskStage -StageArguments @('femm','--fields-only')
            Invoke-AirDeskStage -StageArguments @('offset')
            Invoke-AirDeskStage -StageArguments @('spice','--full')
            Invoke-AirDeskStage -StageArguments @('plots')
            Invoke-AirDeskStage -StageArguments @('demo','--export','--gif')
            Write-Output 'Numerical stages complete. Follow README.md to run the separate Fusion stages.'
        }
        'Export' {
            Invoke-AirDeskStage -StageArguments @('demo','--export','--gif')
            Invoke-AirDeskStage -StageArguments @('cad-gif')
        }
        'Test' {
            & $taskPython -m pytest -q -p no:cacheprovider --junitxml=results/tests.xml
            if ($LASTEXITCODE -ne 0) { throw 'AirDesk tests failed.' }
        }
        'Report' { Invoke-AirDeskStage -StageArguments @('report') }
    }
} finally { Pop-Location }
