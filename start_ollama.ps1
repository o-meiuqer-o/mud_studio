$OllamaDir = "d:\portfolio\ollama_bin"
$ModelsDir = "d:\portfolio\ollama_models"

$env:OLLAMA_MODELS = $ModelsDir

if (Test-Path "$OllamaDir\ollama.exe") {
    Write-Host "Starting Portable Ollama server..." -ForegroundColor Cyan
    Write-Host "Models directory: $ModelsDir" -ForegroundColor Gray
    Start-Process -FilePath "$OllamaDir\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    Write-Host "Ollama is running in the background." -ForegroundColor Green
    Write-Host "You can now run 'python evaluate_websites_local.py' to start evaluation." -ForegroundColor Yellow
} else {
    Write-Host "Error: Ollama executable not found in $OllamaDir" -ForegroundColor Red
}
