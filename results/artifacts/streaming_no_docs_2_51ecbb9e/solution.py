#!/usr/bin/env python3
"""Transcribe an audio file by streaming it to AssemblyAI's real-time API."""

import json
import os
import sys
import threading
import time
import wave

from assemblyai.streaming.v3 import (
    BeginEvent,
    Encoding,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
    TerminationEvent,
    TurnEvent,
)

CHUNK_MS = 50  # size of each simulated "live" audio chunk


def main():
    if len(sys.argv) < 2:
        print("Usage: python solution.py <audio_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("ASSEMBLYAI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    with wave.open(audio_path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width != 2:
        print("Expected 16-bit PCM audio", file=sys.stderr)
        sys.exit(1)
    if channels != 1:
        print("Expected mono audio", file=sys.stderr)
        sys.exit(1)

    turns = {}  # turn_order -> latest transcript text for that turn
    done_event = threading.Event()
    error_holder = {}

    def on_begin(client, event: BeginEvent):
        pass

    def on_turn(client, event: TurnEvent):
        turns[event.turn_order] = event.transcript

    def on_termination(client, event: TerminationEvent):
        done_event.set()

    def on_error(client, error: RealTimeError):
        error_holder["error"] = str(error)
        done_event.set()

    client = RealTimeTranscriber(api_key=api_key)
    client.on(RealTimeEvents.Begin, on_begin)
    client.on(RealTimeEvents.Turn, on_turn)
    client.on(RealTimeEvents.Termination, on_termination)
    client.on(RealTimeEvents.Error, on_error)

    client.connect(
        RealTimeParameters(
            sample_rate=sample_rate,
            encoding=Encoding.pcm_s16le,
            format_turns=True,
        )
    )

    bytes_per_chunk = int(sample_rate * sample_width * (CHUNK_MS / 1000.0))
    bytes_per_chunk -= bytes_per_chunk % sample_width  # keep sample alignment

    def audio_chunks():
        for i in range(0, len(frames), bytes_per_chunk):
            yield frames[i : i + bytes_per_chunk]
            time.sleep(CHUNK_MS / 1000.0)

    client.stream(audio_chunks())

    client.disconnect(terminate=True)

    done_event.wait(timeout=30)

    if "error" in error_holder:
        print(f"Streaming error: {error_holder['error']}", file=sys.stderr)
        sys.exit(1)

    final_text = " ".join(turns[k] for k in sorted(turns.keys())).strip()

    print(json.dumps({"text": final_text}))


if __name__ == "__main__":
    main()
