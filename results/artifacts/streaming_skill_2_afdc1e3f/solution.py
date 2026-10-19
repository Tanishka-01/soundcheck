import asyncio
import json
import os
import sys
import wave

import websockets

API_KEY = os.environ["ASSEMBLYAI_API_KEY"]
STREAMING_URL = "wss://streaming.assemblyai.com/v3/ws"
CHUNK_MS = 50


def load_pcm16_mono(path):
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM audio, got sample width {sampwidth}")

    if channels > 1:
        import audioop

        frames = audioop.tomono(frames, sampwidth, 0.5, 0.5)

    return frames, framerate


async def transcribe(path):
    audio, sample_rate = load_pcm16_mono(path)

    bytes_per_sample = 2
    chunk_size = int(sample_rate * (CHUNK_MS / 1000.0)) * bytes_per_sample

    url = (
        f"{STREAMING_URL}?sample_rate={sample_rate}"
        f"&encoding=pcm_s16le&speech_model=universal-3-6-pro"
    )

    turns = {}
    termination_event = asyncio.Event()

    async with websockets.connect(
        url,
        additional_headers={"Authorization": API_KEY},
    ) as ws:

        async def receiver():
            async for message in ws:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "Turn" and data.get("end_of_turn"):
                    turns[data["turn_order"]] = data.get("transcript", "")
                elif msg_type == "Termination":
                    termination_event.set()
                    break

        async def sender():
            for offset in range(0, len(audio), chunk_size):
                chunk = audio[offset : offset + chunk_size]
                await ws.send(chunk)
                await asyncio.sleep(CHUNK_MS / 1000.0)
            await ws.send(json.dumps({"type": "Terminate"}))

        recv_task = asyncio.create_task(receiver())
        await sender()
        await asyncio.wait_for(termination_event.wait(), timeout=30)
        recv_task.cancel()

    final_text = " ".join(turns[k] for k in sorted(turns.keys()) if turns[k])
    return final_text


def main():
    if len(sys.argv) != 2:
        print("Usage: python solution.py <audio_file>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    text = asyncio.run(transcribe(path))
    print(json.dumps({"text": text}))


if __name__ == "__main__":
    main()
