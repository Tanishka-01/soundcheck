import json
import os
import sys
import time
import wave

import assemblyai.streaming.v3 as aai_streaming


def chunk_wav(path, chunk_ms=50):
    """Yield raw PCM16LE chunks from a mono wav file, paced like live audio."""
    with wave.open(path, "rb") as wf:
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()
        channels = wf.getnchannels()
        frames_per_chunk = max(1, int(sample_rate * chunk_ms / 1000))
        bytes_per_frame = sample_width * channels

        while True:
            frames = wf.readframes(frames_per_chunk)
            if not frames:
                break
            yield frames, len(frames) / bytes_per_frame / sample_rate


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    api_key = os.environ["ASSEMBLYAI_API_KEY"]

    with wave.open(audio_path, "rb") as wf:
        sample_rate = wf.getframerate()

    finals = []
    state = {"done": False, "error": None}

    client = aai_streaming.StreamingClient(api_key=api_key)

    def on_begin(c, event):
        pass

    def on_turn(c, event):
        if event.end_of_turn and event.transcript:
            finals.append((event.turn_order, event.transcript))

    def on_termination(c, event):
        state["done"] = True

    def on_error(c, error):
        state["error"] = str(error)
        state["done"] = True

    client.on(aai_streaming.RealTimeEvents.Begin, on_begin)
    client.on(aai_streaming.RealTimeEvents.Turn, on_turn)
    client.on(aai_streaming.RealTimeEvents.Termination, on_termination)
    client.on(aai_streaming.RealTimeEvents.Error, on_error)

    client.connect(
        aai_streaming.RealTimeParameters(
            sample_rate=sample_rate,
            encoding=aai_streaming.Encoding.pcm_s16le,
            format_turns=True,
        )
    )

    try:
        for frames, duration_s in chunk_wav(audio_path):
            if state["done"]:
                break
            client.stream(frames)
            time.sleep(duration_s)
    finally:
        client.disconnect(terminate=True)

    finals.sort(key=lambda item: item[0])
    final_text = " ".join(text for _, text in finals).strip()

    print(json.dumps({"text": final_text}))


if __name__ == "__main__":
    main()
