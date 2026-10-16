[CmdletBinding()]
param()

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$entryPoint = Join-Path $PSScriptRoot 'run.py'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment not found at .venv. Run: py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

& $python $entryPoint
exit $LASTEXITCODE
