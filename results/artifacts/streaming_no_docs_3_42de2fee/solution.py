import json
import os
import sys
import threading
import time
import wave

import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    Encoding,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    StreamingClient,
    StreamingClientOptions,
    TerminationEvent,
    TurnEvent,
)


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    api_key = os.environ["ASSEMBLYAI_API_KEY"]

    with wave.open(audio_path, "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        audio_bytes = wf.readframes(wf.getnframes())

    if channels != 1 or sampwidth != 2:
        print(
            f"Expected mono 16-bit PCM audio, got channels={channels} sampwidth={sampwidth}",
            file=sys.stderr,
        )
        sys.exit(1)

    turns = {}
    done_event = threading.Event()
    error_holder = {}

    def on_begin(client, event: BeginEvent):
        print(f"Session started: {event.id}", file=sys.stderr)

    def on_turn(client, event: TurnEvent):
        if event.end_of_turn:
            turns[event.turn_order] = event.transcript

    def on_termination(client, event: TerminationEvent):
        done_event.set()

    def on_error(client, error: RealTimeError):
        error_holder["error"] = error
        done_event.set()

    client = StreamingClient(StreamingClientOptions(api_key=api_key))
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

    # Stream the file's audio in small chunks, paced at real-time speed, so
    # the server sees it the way it would see a live microphone feed.
    chunk_duration_s = 0.1
    chunk_size = int(sample_rate * sampwidth * chunk_duration_s)

    try:
        for offset in range(0, len(audio_bytes), chunk_size):
            if done_event.is_set():
                break
            chunk = audio_bytes[offset : offset + chunk_size]
            client.stream(chunk)
            time.sleep(chunk_duration_s)

        client.disconnect(terminate=True)
    finally:
        done_event.wait(timeout=10)

    if "error" in error_holder:
        print(f"Streaming error: {error_holder['error']}", file=sys.stderr)
        sys.exit(1)

    final_text = " ".join(turns[key] for key in sorted(turns.keys())).strip()
    print(json.dumps({"text": final_text}))


if __name__ == "__main__":
    main()
