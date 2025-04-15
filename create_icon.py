from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    # Create a new image with a white background
    size = (256, 256)
    image = Image.new('RGBA', size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a rounded rectangle for the notepad
    padding = 40
    rect_bounds = [padding, padding, size[0]-padding, size[1]-padding]
    draw.rounded_rectangle(rect_bounds, radius=20, fill="#0078d4")
    
    # Draw some lines to represent text
    line_padding = 70
    line_height = 20
    line_color = "#ffffff"
    line_lengths = [120, 140, 100]  # Different lengths for visual interest
    
    for i, length in enumerate(line_lengths):
        y = line_padding + (i * line_height * 2)
        draw.rectangle([padding+20, y, padding+20+length, y+line_height], fill=line_color)
    
    # Save in different sizes
    image.save("icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

if __name__ == "__main__":
    create_icon() 