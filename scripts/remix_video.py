"""
CLI tool to remix an existing video using the OpenAI API.

This script expects two positional arguments:
    1. video_id: The ID of the source video to remix.
    2. prompt:   A text description of how to modify or remix the video.

Example:
    python scripts/remix_video.py VIDEO_ID "Make the character hold a lobster instead of a lime."
"""
import argparse
from openai import OpenAI


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the remix video CLI."""
    parser = argparse.ArgumentParser(
        description="Remix an existing video using the OpenAI API."
    )
    parser.add_argument("video_id", help="The ID of the source video to remix.")
    parser.add_argument("prompt", help="The text prompt describing how to remix the video.")
    return parser


def main() -> None:
    """Parse CLI arguments and send the remix request to the OpenAI API."""
    parser = build_parser()
    args = parser.parse_args()

    client = OpenAI()
    video = client.videos.remix(
        video_id=args.video_id,
        prompt=args.prompt,
    )
    print(video.id)


if __name__ == "__main__":
    main()
