"""One-off precondition check (not part of the harness): makes ONE direct,
correct AssemblyAI call per task (transcribe, speakers, streaming) against
data/sample.wav, using the current docs' recommended SDK usage, and checks
the result against data/keywords.txt / expected speaker count.

Run: .venv\\Scripts\\python verify_assemblyai.py [transcribe|speakers|streaming]
(no arg runs all three)
"""
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).parent
SAMPLE_WAV = ROOT / "data" / "sample.wav"
KEYWORDS_TXT = ROOT / "data" / "keywords.txt"
ENV_FILE = ROOT / ".env"


def load_api_key() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASSEMBLYAI_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key
    raise SystemExit("ASSEMBLYAI_API_KEY is not set in .env")


def keyword_hits(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    lowered = text.lower()
    hits = [k for k in keywords if k.lower() in lowered]
    return len(hits), hits


def run_transcribe(aai, keywords):
    print("=== transcribe ===")
    config = aai.TranscriptionConfig(speech_models=["universal-3-5-pro", "universal-2"])
    transcript = aai.Transcriber(config=config).transcribe(str(SAMPLE_WAV))
    if transcript.status == aai.TranscriptStatus.error:
        raise SystemExit(f"transcribe failed: {transcript.error}")
    n, hits = keyword_hits(transcript.text, keywords)
    print(f"text: {transcript.text}")
    print(f"keyword hits: {n}/{len(keywords)} -> {hits}")
    print("PASS" if n >= len(keywords) * 0.6 else "FAIL (too few keywords matched)")
    print()


def run_speakers(aai, keywords):
    print("=== speakers ===")
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-5-pro", "universal-2"], speaker_labels=True
    )
    transcript = aai.Transcriber(config=config).transcribe(str(SAMPLE_WAV))
    if transcript.status == aai.TranscriptStatus.error:
        raise SystemExit(f"speakers failed: {transcript.error}")
    speakers = sorted({u.speaker for u in (transcript.utterances or [])})
    n, hits = keyword_hits(transcript.text, keywords)
    print(f"text: {transcript.text}")
    print(f"distinct speakers: {speakers}")
    print(f"keyword hits: {n}/{len(keywords)} -> {hits}")
    ok = len(speakers) >= 2 and n >= len(keywords) * 0.6
    print("PASS" if ok else "FAIL (need >=2 speakers and enough keywords)")
    print()


def run_streaming(api_key, keywords):
    print("=== streaming ===")
    from assemblyai.streaming.v3 import (
        BeginEvent,
        StreamingClient,
        StreamingClientOptions,
        StreamingError,
        StreamingEvents,
        StreamingParameters,
        TerminationEvent,
        TurnEvent,
    )

    finals = []

    def on_begin(_client, event: BeginEvent):
        print(f"streaming session began: id={event.id}")

    def on_turn(_client, event: TurnEvent):
        print(f"  turn: end_of_turn={event.end_of_turn} transcript={event.transcript!r}")
        if event.end_of_turn and event.transcript:
            finals.append(event.transcript)

    def on_terminated(_client, event: TerminationEvent):
        print(f"streaming session terminated: {event.audio_duration_seconds}s processed")

    def on_error(_client, error: StreamingError):
        print(f"streaming ERROR: {error}")

    client = StreamingClient(StreamingClientOptions(api_key=api_key, terminate_timeout=20.0))
    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)
    client.connect(StreamingParameters(sample_rate=16000, speech_model="universal-3-5-pro"))

    with wave.open(str(SAMPLE_WAV), "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2
        chunk_frames = 3200  # ~200ms at 16kHz
        chunks = []
        while True:
            frames = w.readframes(chunk_frames)
            if not frames:
                break
            chunks.append(frames)
    print(f"sending {len(chunks)} chunks (~200ms each)")

    t0 = time.time()
    client.stream(iter(chunks))
    print(f"stream() returned after {time.time() - t0:.1f}s, waiting before disconnect...")
    time.sleep(55.0)  # server throttles ingestion to ~1.25x realtime; ~62s audio needs ~50s
    client.disconnect(terminate=True)
    print(f"disconnect() returned after {time.time() - t0:.1f}s total")

    full_text = " ".join(finals)
    n, hits = keyword_hits(full_text, keywords)
    print(f"final turns text: {full_text}")
    print(f"keyword hits: {n}/{len(keywords)} -> {hits}")
    print("PASS" if n >= len(keywords) * 0.6 else "FAIL (too few keywords matched)")


def main():
    import assemblyai as aai

    api_key = load_api_key()
    aai.settings.api_key = api_key
    keywords = KEYWORDS_TXT.read_text(encoding="utf-8").splitlines()
    only = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"Sample audio: {SAMPLE_WAV}")
    print(f"Keywords ({len(keywords)}): {keywords}")
    print()

    if only in (None, "transcribe"):
        run_transcribe(aai, keywords)
    if only in (None, "speakers"):
        run_speakers(aai, keywords)
    if only in (None, "streaming"):
        run_streaming(api_key, keywords)


if __name__ == "__main__":
    main()
