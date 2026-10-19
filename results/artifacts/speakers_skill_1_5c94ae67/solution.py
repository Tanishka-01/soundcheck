import json
import os
import sys

import assemblyai as aai


def main():
    audio_path = sys.argv[1]

    aai.settings.api_key = os.environ["ASSEMBLYAI_API_KEY"]

    config = aai.TranscriptionConfig(
        speaker_labels=True,
    )

    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        print(f"Transcription failed: {transcript.error}", file=sys.stderr)
        sys.exit(1)

    speakers = []
    for utterance in transcript.utterances or []:
        if utterance.speaker not in speakers:
            speakers.append(utterance.speaker)

    result = {"text": transcript.text, "speakers": speakers}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
