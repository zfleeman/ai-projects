# pylint: disable=C0116
"""
A simple Discord Bot that utilizes the OpenAI API.
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

import discord
from discord import Embed, FFmpegOpusAudio, Intents, Interaction, app_commands
from openai import BadRequestError
from openai.types import Image, ImagesResponse

from ai_helpers import (
    check_model_limit,
    content_path,
    download_file_from_url,
    generate_speech,
    get_config,
    get_openai_client,
    new_response,
    speak_and_spell,
)
from db_utils import create_command_context

# Bot Client
intents = Intents.default()
intents.messages = True
intents.guilds = True

bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

USER_AGENT = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3"
usage_tracker = {}  # blank dict created to store model usage for restricted models


@tree.command(name="join", description="Join the voice channel that the user is currently in.")
async def join(interaction: Interaction) -> None:
    context = await create_command_context(interaction)

    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message(content="I have joined the voice chat.", delete_after=3.0)
    else:
        await interaction.response.send_message(content=f"{interaction.user.name} is not in a voice channel.")

    return await context.save()


@tree.command(name="leave", description="Leave the voice channel that the bot is currently in.")
async def leave(interaction: Interaction) -> None:
    context = await create_command_context(interaction)

    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message(content="I have left the voice chat.", delete_after=3.0)

    return await context.save()


@tree.command(name="clean", description="Delete messages sent by the bot within a specified timeframe.")
@app_commands.describe(number_of_minutes="The number of minutes to look back for message deletion.")
async def clean(interaction: Interaction, number_of_minutes: int) -> None:
    context = await create_command_context(interaction, params={"number_of_minutes": number_of_minutes})
    config = get_config()

    max_clean_minutes = int(config.get("GENERAL", "max_clean_minutes", fallback=1440))
    if max_clean_minutes < number_of_minutes:
        await interaction.response.send_message(content=f"Can't clean more than {max_clean_minutes} minutes back.")
        return

    after_time = datetime.now() - timedelta(minutes=number_of_minutes)
    messages = interaction.channel.history(after=after_time)

    bot_id = bot.user.id
    sleep_seconds = float(config.get("GENERAL", "clean_sleep", fallback=0.75))

    await interaction.response.send_message(content="Deleting messages...")

    async for message in messages:
        if message.author.id == bot_id:
            await asyncio.sleep(sleep_seconds)
            await message.delete()

    return await context.save()


@tree.command(name="talk", description="Start a loop where the bot talks about a specified topic at regular intervals.")
@app_commands.describe(
    topic="The topic the bot will talk about.", wait_minutes="The interval in minutes between each message."
)
async def talk(interaction: Interaction, topic: Literal["nonsense", "quotes"], wait_minutes: float = 5.0) -> None:
    context = await create_command_context(interaction, params={"topic": f"talk_{topic}", "wait_minutes": wait_minutes})
    interval = wait_minutes * 60

    config = get_config()
    prompt = config.get("PROMPTS", topic)

    if not discord.utils.get(bot.voice_clients, guild=interaction.guild):
        await interaction.response.send_message(content="I must be in a voice channel before you use this command.")
        return

    await interaction.response.send_message(content="Starting talk loop.", delete_after=3.0)

    while True:

        # check to see if a voice connection is still active
        if voice := discord.utils.get(bot.voice_clients, guild=interaction.guild):

            tts, file_path = await speak_and_spell(
                context=context,
                prompt=prompt,
            )
            source = FFmpegOpusAudio(file_path)
            _ = voice.play(source)

            # create our file object
            discord_file = discord.File(fp=file_path, filename=file_path.name)

            await interaction.channel.send(content=tts, file=discord_file)
            await asyncio.sleep(interval)
        else:
            break

    return await context.save()


@tree.command(name="rather", description="Play a 'Would You Rather' game with a specified topic.")
@app_commands.describe(topic="The subject for the generated hypothetical question.")
async def rather(interaction: Interaction, topic: Literal["normal", "adult", "games", "fitness"] = "normal") -> None:
    context = await create_command_context(interaction, params={"topic": f"rather_{topic}"})
    config = get_config()
    topic = f"rather_{topic}"
    new_hypothetical_prompt = config.get("PROMPTS", "new_hypothetical")

    await interaction.response.defer()

    tts, file_path = await speak_and_spell(
        context=context,
        prompt=new_hypothetical_prompt,
    )

    # play over a voice channel
    if voice := discord.utils.get(bot.voice_clients, guild=interaction.guild):
        source = FFmpegOpusAudio(file_path)
        _ = voice.play(source)

    # create our file object
    discord_file = discord.File(file_path, filename=file_path.name)

    await interaction.followup.send(content=tts, file=discord_file)

    return await context.save()


@tree.command(name="say", description="Make the bot say a specified text.")
@app_commands.describe(text_to_speech="The text you want the bot to say.", voice="The OpenAI voice model to use.")
async def say(
    interaction: Interaction,
    text_to_speech: str,
    voice: Literal["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"] = "onyx",
) -> None:
    context = await create_command_context(interaction, params={"text_to_speech": text_to_speech, "voice": voice})
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{ts}.wav"
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    await interaction.response.defer()

    file_path = await generate_speech(
        context=context,
        file_name=file_name,
        tts=text_to_speech,
        voice=voice,
    )

    if voice_client:
        source = FFmpegOpusAudio(file_path)
        _ = voice_client.play(source)

    # create our file object
    discord_file = discord.File(fp=file_path, filename=file_path.name)

    await interaction.followup.send(content=text_to_speech, file=discord_file)

    return await context.save()


@tree.command(name="image", description="Generate an image using a prompt and a specified model.")
@app_commands.describe(
    image_prompt="The prompt used for image generation.",
    image_model="The OpenAI image model to use.",
    background="Allows to set transparency for the background of the generated image(s). gpt-image-1 only.",
)
async def image(
    interaction: Interaction,
    image_prompt: str,
    image_model: Literal["dall-e-2", "dall-e-3", "gpt-image-1", "gpt-image-1-mini"] = "gpt-image-1-mini",
    background: Literal["transparent", "opaque", "auto"] = "auto",
) -> None:
    context = await create_command_context(
        interaction, params={"prompt": image_prompt, "model": image_model, "background": background}
    )
    submission_params = context.params

    await interaction.response.defer()

    openai_client = await get_openai_client(interaction.guild_id)

    # create our embed object
    embed = Embed(
        color=10181046,
        title=f"`{image_model}` Image Generation",
        description=f"### User Input:\n> {image_prompt}",
    )

    # gpt-image-1 has some special use cases that don't apply to dall-e-2/3
    if "gpt-image-1" not in image_model:
        _ = submission_params.pop("background")
        submission_params["response_format"] = "b64_json"
    else:

        if not check_model_limit(context=context, usage_tracker=usage_tracker):

            await interaction.followup.send(
                content=f"`{context.params['model']}` been used too much today. Try again tomorrow!"
            )

            return

        submission_params["moderation"] = "low"

        # set a footer showing usage information for gpt-image-1 (not mini)
        if image_model == "gpt-image-1":
            embed.set_footer(
                text=(
                    f"Used {usage_tracker[interaction.guild_id][image_model]['count']} "
                    f"out of {usage_tracker[interaction.guild_id][image_model]['limit']} "
                    f"image generations with {image_model} today."
                )
            )

    try:
        image_response: ImagesResponse = await openai_client.images.generate(**submission_params)
    except BadRequestError:
        await interaction.followup.send(
            f"Your prompt:\n> {image_prompt}\nProbably violated OpenAI's content policies. Clean up your act."
        )
        return

    image_object: Image = image_response.data[0]

    # save the generated image to a file
    file_name = f"{image_model}-{image_response.created}.png"
    path = content_path(context=context, file_name=file_name)
    image_bytes = base64.b64decode(image_object.b64_json)

    with open(path, "wb") as file:
        file.write(image_bytes)

    embed.set_image(url=f"attachment://{file_name}")

    # set the footer text if this is dall-e-3
    if image_object.revised_prompt:
        embed.set_footer(text=f"Revised Prompt:\n{image_object.revised_prompt}")

    # attach our file object
    file_upload = discord.File(fp=path, filename=file_name)

    await interaction.followup.send(file=file_upload, embed=embed)

    return await context.save()


@tree.command(name="video", description="Generate a video using a prompt.")
@app_commands.describe(
    video_prompt="The prompt used for video generation.",
    model="The OpenAI video model to use.",
    image_reference="Upload a reference image for the model to work with.",
    seconds="Total duration in seconds.",
    size="The video's output resolution.",
    ai_director="Punch-up your prompt with keywords and information important to the video model.",
)
async def video(
    interaction: Interaction,
    video_prompt: str,
    image_reference: Optional[discord.Attachment] = None,
    model: Literal["sora-2", "sora-2-pro"] = "sora-2",
    seconds: Literal["4", "8", "12"] = "4",
    size: Literal["720x1280", "1280x720"] = "1280x720",
    ai_director: bool = True,
) -> None:
    context = await create_command_context(
        interaction,
        params={"prompt": video_prompt, "model": model, "seconds": seconds, "size": size},
    )

    await interaction.response.defer()

    if interaction.user.id != 222869237012758529:
        await interaction.followup.send("Only Zach can use this command.")
        return

    config = get_config()
    original_prompt = video_prompt
    description_text = f"### User Input:\n> {original_prompt}"

    openai_client = await get_openai_client(guild_id=0)

    if image_reference:
        # Download the image using the generic function
        download_file_from_url(
            url=image_reference.url,
            filename=image_reference.filename,
            headers={"User-Agent": USER_AGENT},
        )
        input_reference_path = image_reference.filename

        # Open the file, read its contents, and store as bytes (to avoid closed file issues)
        with open(input_reference_path, "rb") as input_reference:
            context.params["input_reference"] = (image_reference.filename, input_reference.read())

    if ai_director:
        instructions = config.get("OPENAI_INSTRUCTIONS", "video").format(seconds=seconds)
        response = await new_response(context=context, instructions=instructions, prompt=video_prompt)
        context.params["prompt"] = response.output_text
        description_text += "\n### AI Director:\n`True`"

    video_object = await openai_client.videos.create_and_poll(**context.params)

    try:
        # successful generation
        if video_object.status == "completed":
            content = await openai_client.videos.download_content(video_object.id, variant="video")
            video_file_name = f"{model}-{video_object.id}.mp4"
            video_path = content_path(context=context, file_name=video_file_name)
            content.write_to_file(video_path)

            files = []
            files.append(discord.File(fp=video_path, filename=video_file_name))

            if ai_director:
                text_file_name = f"{model}-ai-director-prompt-{video_object.id}.txt"
                text_path = content_path(context=context, file_name=text_file_name)

                with open(text_path, "w", encoding="UTF-8") as f:
                    f.write(response.output_text)

                files.append(discord.File(fp=text_path, filename=text_file_name))

            # create our embed object
            embed = Embed(
                color=3426654,
                title=f"`{model}` Video Generation",
                description=description_text,
            )

            if image_reference:
                embed.set_image(url=f"attachment://{image_reference.filename}")
                # Only attach the file if it still exists (avoid I/O on closed file)
                if Path(image_reference.filename).exists():
                    files.append(discord.File(fp=image_reference.filename, filename=image_reference.filename))
                    # delete downloaded file after sending
                    embed.set_footer(text="Used image for reference.")

            # attach our files object
            await interaction.followup.send(embed=embed, files=files)

        # unsuccessful generation
        else:
            await interaction.followup.send(
                content=(
                    f"Video ID, `{video_object.id}`, has status `{video_object.status}`.\n\n"
                    f"ERROR: `{video_object.error.code}`\nMESSAGE: `{video_object.error.message}`\n\n"
                    "Guidelines and restrictions for video models: "
                    "https://platform.openai.com/docs/guides/video-generation#guardrails-and-restrictions"
                )
            )

            # write text file with a failed name
            if ai_director:
                text_file_name = f"FAILED-{model}-ai-director-prompt-{video_object.id}.txt"
                text_path = content_path(context=context, file_name=text_file_name)

                with open(text_path, "w", encoding="UTF-8") as f:
                    f.write(response.output_text)
    finally:
        # delete the image reference file if it exists
        if image_reference and Path(image_reference.filename).exists():
            Path(image_reference.filename).unlink()

    context.params["ai_director"] = ai_director
    return await context.save()


@tree.command(name="vision", description="Describe or interpret an image using a prompt.")
@app_commands.describe(
    attachment="The image file you want to describe or interpret.",
    vision_prompt="The prompt to be used when describing the image.",
)
async def vision(interaction: Interaction, attachment: discord.Attachment, vision_prompt: str = "") -> None:
    context = await create_command_context(
        interaction, params={"vision_prompt": vision_prompt, "attachment": attachment.filename}
    )
    config = get_config()

    if not vision_prompt:
        vision_prompt = config.get("PROMPTS", "vision_prompt", fallback="What is in this image?")

    try:
        image_url = attachment.url
    except IndexError:
        await interaction.response.send_message(
            "```plaintext\nError: Unable to retrieve the image attachment. Did you attach an image?\n```"
        )
        return

    await interaction.response.defer()

    openai_client = await get_openai_client(interaction.guild_id)

    response = await openai_client.responses.create(
        model=config.get("OPENAI_GENERAL", "vision_model", fallback="gpt-5-mini"),
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": vision_prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
        max_output_tokens=config.getint("OPENAI_GENERAL", "max_output_tokens", fallback=500),
    )

    embed = Embed(
        color=5763719,
        title="Vision Response",
        description=f"User Input:\n```{vision_prompt}```",
    )

    # Download the image using the generic function
    download_file_from_url(
        url=attachment.url,
        filename=attachment.filename,
        headers={"User-Agent": USER_AGENT},
    )

    discord_file = discord.File(fp=attachment.filename, filename=attachment.filename)

    embed.set_image(url=f"attachment://{attachment.filename}")
    embed.set_footer(text=response.output_text)

    await interaction.followup.send(embed=embed, file=discord_file)

    Path(attachment.filename).unlink()

    return await context.save()


@tree.command(name="chat", description="Have a conversation with an OpenAI Chat Model, like you would with ChatGPT.")
@app_commands.describe(
    chat_prompt="The text of your question or statement that you wan the Chat Model to address.",
    keep_chatting="Continue the conversation from your last prompt.",
    chat_model="The OpenAI Chat Model to use.",
    custom_instructions="Help the Chat Model respond to your prompt the way YOU want it to.",
)
async def chat(
    interaction: Interaction,
    chat_prompt: str,
    keep_chatting: Literal["Yes", "No"] = "No",
    chat_model: Literal["gpt-5-mini", "gpt-5", "gpt-4.1", "gpt-4.1-mini"] = "gpt-4.1-mini",
    custom_instructions: Optional[str] = None,
) -> None:

    if not custom_instructions:
        config = get_config()
        custom_instructions = config.get(
            "OPENAI_INSTRUCTIONS",
            "chat_helper",
            fallback="Ensure your response is under 2,000 characters and uses markdown compatible with Discord.",
        )

    context = await create_command_context(
        interaction,
        params={
            "chat_prompt": chat_prompt,
            "topic": str(interaction.user.id),
            "custom_instructions": custom_instructions,
            "keep_chatting": keep_chatting == "Yes",
            "model": chat_model,
        },
    )

    await interaction.response.defer()

    try:
        response = await new_response(
            context=context, prompt=chat_prompt, instructions=custom_instructions, model=chat_model
        )
    except BadRequestError:
        await interaction.followup.send(
            f"Your prompt:\n> {chat_prompt}\nProbably violated OpenAI's content policies. Clean up your act."
        )
        return

    title = f"🤖 `{chat_model}` Response{' (Continued)' if response.previous_response_id else ''}"
    embed = Embed(title=title, description=response.output_text, color=1752220)

    await interaction.followup.send(content=f"> {chat_prompt}", embed=embed)

    return await context.save()


@bot.event
async def on_ready():

    await tree.sync()  # Sync slash commands globally
    print(f"Logged in as {bot.user}")


bot.run(os.getenv("DISCORD_BOT_KEY"))
