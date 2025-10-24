import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from api_keys import api_keys

API_KEY = api_keys["B4NG AI"]
MODEL = "sora-2"
DEFAULT_PROMPT = "A video of a cat on a motorcycle"
DEFAULT_SECONDS = 4

client = AsyncOpenAI(api_key=API_KEY)

ts = datetime.now().strftime("%Y%m%d%H%M%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a video using the specified prompt.")
    parser.add_argument(
        "-p",
        "--prompt",
        dest="prompt_source",
        metavar="PROMPT",
        help="Prompt text or path to a text file containing the prompt.",
    )
    parser.add_argument(
        "-s",
        "--seconds",
        dest="seconds",
        type=int,
        choices=[4, 8, 12],
        metavar="SECONDS",
        help=f"Length of the generated video (default: {DEFAULT_SECONDS}).",
    )
    return parser.parse_args()


def resolve_prompt(prompt_source: Optional[str]) -> str:
    if prompt_source is None:
        return DEFAULT_PROMPT

    prompt_path = Path(prompt_source)
    if prompt_path.is_file():
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        if not prompt_text:
            raise ValueError(f"Prompt file '{prompt_source}' is empty.")
        return prompt_text

    return prompt_source


def resolve_seconds(seconds: Optional[int]) -> int:
    if seconds is None:
        return DEFAULT_SECONDS
    if seconds <= 0:
        raise ValueError("Seconds must be a positive integer.")
    return seconds


async def main(prompt: str, seconds: int) -> None:
    video = await client.videos.create_and_poll(
        model=MODEL,
        prompt=prompt,
        seconds=str(seconds),
    )

    print(video)

    if video.status == "completed":
        print("Video successfully completed: ", video)
    else:
        print("Video creation failed. Status: ", video.status)

    content = await client.videos.download_content(video.id, variant="video")
    content.write_to_file(f"{MODEL}-{ts}.mp4")


if __name__ == "__main__":
    args = parse_args()
    try:
        prompt_value = resolve_prompt(args.prompt_source)
        seconds_value = resolve_seconds(args.seconds)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))

    asyncio.run(main(prompt_value, seconds_value))
