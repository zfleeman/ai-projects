import base64

from openai import OpenAI

client = OpenAI()

result = client.images.edit(
    model="gpt-image-1",
    image=open("normal.png", "rb"),
    mask=open("mask.png", "rb"),
    prompt="A boy is holding a cooking pot that is filled to the brim with a large, boiled watermelon.",
    input_fidelity="high",
    quality="high",
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

# Save the image to a file
with open("boiled_watermelon3.png", "wb") as f:
    f.write(image_bytes)
