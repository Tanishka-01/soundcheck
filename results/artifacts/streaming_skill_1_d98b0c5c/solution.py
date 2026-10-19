import json
import os
import sys
import time
import wave

from assemblyai.streaming.v3 import (
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
)


def main():
    audio_path = sys.argv[1]
    api_key = os.environ["ASSEMBLYAI_API_KEY"]

    turns = {}

    def on_turn(_transcriber, event):
        turns[event.turn_order] = event.transcript

    def on_error(_transcriber, error):
        print(f"stream error: {error}", file=sys.stderr)

    transcriber = RealTimeTranscriber(api_key=api_key)
    transcriber.on(RealTimeEvents.Turn, on_turn)
    transcriber.on(RealTimeEvents.Error, on_error)

    transcriber.connect(
        RealTimeParameters(
            speech_model="universal-3-6-pro",
            sample_rate=16000,
            encoding="pcm_s16le",
        )
    )

    def audio_chunks():
        with wave.open(audio_path, "rb") as wf:
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            channels = wf.getnchannels()
            chunk_seconds = 0.1
            frames_per_chunk = int(sample_rate * chunk_seconds)
            bytes_per_frame = sample_width * channels
            while True:
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break
                start = time.monotonic()
                yield data
                elapsed = time.monotonic() - start
                chunk_duration = len(data) / bytes_per_frame / sample_rate
                sleep_time = chunk_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    try:
        transcriber.stream(audio_chunks())
    finally:
        transcriber.disconnect(terminate=True)

    final_text = " ".join(turns[k] for k in sorted(turns)).strip()
    print(json.dumps({"text": final_text}))


if __name__ == "__main__":
    main()
