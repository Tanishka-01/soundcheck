import sys
import os
import json

import assemblyai as aai


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"text": ""}))
        sys.exit(1)

    audio_path = sys.argv[1]

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY environment variable is not set")

    aai.settings.api_key = api_key

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"Transcription failed: {transcript.error}")

    print(json.dumps({"text": transcript.text or ""}))


if __name__ == "__main__":
    main()
