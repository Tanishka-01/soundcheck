# Synthesizes each line of data/script.txt to its own 16kHz mono 16-bit PCM wav
# using installed SAPI voices. Called by generate_audio.py.
param(
    [Parameter(Mandatory=$true)][string]$OutDir
)

Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono
)

$lines = @(
    @{voice="Microsoft David Desktop"; speaker="David"; text="Hi everyone, thanks for joining. I wanted to talk about planning our team offsite for next quarter."},
    @{voice="Microsoft Zira Desktop";  speaker="Zira";  text="That sounds great. Do we have a location in mind yet, or are we still deciding on that?"},
    @{voice="Microsoft David Desktop"; speaker="David"; text="We're leaning towards a mountain lodge, somewhere quiet with good hiking trails nearby for everyone to enjoy."},
    @{voice="Microsoft Zira Desktop";  speaker="Zira";  text="I love that idea. We should also plan a few team building activities, maybe a cooking class or trivia night."},
    @{voice="Microsoft David Desktop"; speaker="David"; text="Good point. Let's budget three days total, with one day dedicated purely to workshops and planning sessions."},
    @{voice="Microsoft Zira Desktop";  speaker="Zira";  text="Should we invite the remote employees too, or keep this limited to the people in the main office?"},
    @{voice="Microsoft David Desktop"; speaker="David"; text="Definitely invite everyone. We can cover travel costs so nobody feels left out of the offsite."},
    @{voice="Microsoft Zira Desktop";  speaker="Zira";  text="Perfect, I will start a shared document and send out a survey to gather everyone's availability this week."}
)

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$i = 0
foreach ($line in $lines) {
    $i++
    $num = $i.ToString("00")
    $outPath = Join-Path $OutDir "turn_${num}_$($line.speaker).wav"
    $synth.SelectVoice($line.voice)
    $synth.SetOutputToWaveFile($outPath, $fmt)
    $synth.Speak($line.text)
    $synth.SetOutputToNull()
    Write-Output "$outPath|$($line.speaker)|$($line.text)"
}
