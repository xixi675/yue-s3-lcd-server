param(
    [Parameter(Mandatory = $true)][string]$InputJson,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$chars = [System.IO.File]::ReadAllText($InputJson, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() |
    Where-Object {
        $_.Enabled -and
        $_.VoiceInfo.Culture.Name -eq "zh-CN" -and
        $_.VoiceInfo.Gender -eq "Female"
    } |
    Select-Object -First 1

if (-not $voice) {
    $voice = $synth.GetInstalledVoices() |
        Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq "zh-CN" } |
        Select-Object -First 1
}
if (-not $voice) {
    throw "No installed zh-CN speech voice was found."
}

$synth.SelectVoice($voice.VoiceInfo.Name)
$synth.Rate = -1
$synth.Volume = 100

for ($index = 0; $index -lt $chars.Count; $index++) {
    $path = Join-Path $OutputDir ("{0:D3}.wav" -f $index)
    $synth.SetOutputToWaveFile($path)
    $synth.Speak([string]$chars[$index])
}

$synth.Dispose()
