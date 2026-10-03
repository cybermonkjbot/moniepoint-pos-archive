"""Remove transparent vertical margins from the client-supplied loading logo."""
from pathlib import Path
from PIL import Image

source = Path("/Users/joshua/Downloads/images-removebg-preview.png")
target = Path(__file__).resolve().parents[1] / "moniepoint_pos/public/images/k3ls-loading-logo.png"
image = Image.open(source).convert("RGBA")
bounds = image.getchannel("A").getbbox()
if bounds is None:
    raise ValueError("The logo is empty.")
box = (0, max(0, bounds[1] - 6), image.width, min(image.height, bounds[3] + 6))
image.crop(box).save(target)
print(f"Saved {target}, {image.width} x {box[3] - box[1]} pixels, crop {box}")
