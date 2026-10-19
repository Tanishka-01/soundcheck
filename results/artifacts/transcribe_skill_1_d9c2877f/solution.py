import json
import os
import sys

import assemblyai as aai


def main() -> None:
    audio_path = sys.argv[1]

    aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(transcript.error)

    print(json.dumps({"text": transcript.text}))


if __name__ == "__main__":
    main()
