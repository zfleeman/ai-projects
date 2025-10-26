import argparse
import os

from openai import OpenAI

API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=API_KEY)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a video by video id using OpenAI API.")
    parser.add_argument("-v", "--video-id", type=str, help="The ID of the video to download")
    args = parser.parse_args()

    video_id = args.video_id
    # Download the video using OpenAI client
    response = client.videos.download_content(video_id=video_id)
    # Save the video to a file named after the video id
    with open(f"{video_id}.mp4", "wb") as f:
        f.write(response.content)
    print(f"Video {video_id} downloaded as {video_id}.mp4")
