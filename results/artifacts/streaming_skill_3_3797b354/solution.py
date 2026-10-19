import asyncio
import json
import os
import sys
import wave

import websockets

STREAMING_URL = "wss://streaming.assemblyai.com/v3/ws"
CHUNK_MS = 50


async def transcribe(audio_path: str) -> str:
    api_key = os.environ["ASSEMBLYAI_API_KEY"]

    with wave.open(audio_path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise ValueError(f"Expected 16-bit PCM audio, got sample width {sample_width}")
    if channels != 1:
        raise ValueError(f"Expected mono audio, got {channels} channels")

    bytes_per_chunk = int(sample_rate * (CHUNK_MS / 1000.0) * sample_width)

    url = f"{STREAMING_URL}?sample_rate={sample_rate}&encoding=pcm_s16le&speech_model=universal-3-6-pro"

    finalized_turns = {}
    done = asyncio.Event()

    async with websockets.connect(
        url, additional_headers={"Authorization": api_key}
    ) as ws:

        async def receiver():
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "Turn":
                    if msg.get("end_of_turn"):
                        finalized_turns[msg["turn_order"]] = msg.get("transcript", "")
                elif msg_type == "Termination":
                    done.set()
                    break

        recv_task = asyncio.create_task(receiver())

        for offset in range(0, len(frames), bytes_per_chunk):
            chunk = frames[offset : offset + bytes_per_chunk]
            if not chunk:
                continue
            await ws.send(chunk)
            await asyncio.sleep(CHUNK_MS / 1000.0)

        await ws.send(json.dumps({"type": "Terminate"}))

        try:
            await asyncio.wait_for(done.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass

        recv_task.cancel()
        try:
            await recv_task
        except (asyncio.CancelledError, Exception):
            pass

    return " ".join(finalized_turns[k] for k in sorted(finalized_turns))


def main():
    audio_path = sys.argv[1]
    text = ""
    try:
        text = asyncio.run(transcribe(audio_path))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
    finally:
        print(json.dumps({"text": text}))


if __name__ == "__main__":
    main()
