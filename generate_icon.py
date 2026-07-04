import os
import sys

def generate_blue_app_icon(output_path="app_icon.ico"):
    """
    使用 Python Pillow 库动态生成一个精致现代的 '浅蓝与淡蓝配色圆角方形' 矢量质感图标，
    并自动生成包含 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 等多尺寸的标准 Windows .ico 图标文件。
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # 如果未安装 Pillow，先尝试在后台安装
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
        from PIL import Image, ImageDraw

    # 创建一个 512x512 的高保真画布（方便生成 256x256 的高清 Windows 图标）
    size = 512
    # 浅蓝 (#5DADE2) 与淡蓝 (#AED6F1) 配色渐变
    # 主圆角背景色：清爽科技淡蓝
    bg_color = (174, 214, 241)     # 淡蓝 #AED6F1
    inner_color = (93, 173, 226)   # 浅蓝 #5DADE2
    white_color = (255, 255, 255)  # 纯白

    # 1. 创建带透明度的 RGBA 图像
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # 2. 绘制圆角方形底色板
    radius = 110  # 优雅的圆角弧度
    draw.rounded_rectangle(
        [(40, 40), (size - 40, size - 40)],
        radius=radius,
        fill=bg_color,
        outline=(255, 255, 255, 40),
        width=4
    )

    # 3. 绘制内部浅色微层级圆角矩形（拟物渐变感）
    draw.rounded_rectangle(
        [(75, 75), (size - 75, size - 75)],
        radius=radius - 20,
        fill=inner_color,
        outline=(255, 255, 255, 60),
        width=2
    )

    # 4. 在中心绘制精致的书写/记事本矢量轮廓
    # 绘制白色的记事本背景
    pad_left, pad_top, pad_right, pad_bottom = 150, 140, size - 150, size - 140
    draw.rounded_rectangle(
        [(pad_left, pad_top), (pad_right, pad_bottom)],
        radius=25,
        fill=white_color
    )

    # 绘制记事本上方的浅蓝侧扣（3个小圆圈代表铁环夹）
    ring_radius = 12
    draw.ellipse([(pad_left + 40, pad_top - 20), (pad_left + 40 + ring_radius*2, pad_top + 4)], fill=bg_color)
    draw.ellipse([(size // 2 - ring_radius, pad_top - 20), (size // 2 + ring_radius, pad_top + 4)], fill=bg_color)
    draw.ellipse([(pad_right - 64, pad_top - 20), (pad_right - 64 + ring_radius*2, pad_top + 4)], fill=bg_color)

    # 绘制书写横线
    line_color = (133, 193, 233, 255)  # 优雅淡蓝线条
    draw.rounded_rectangle([(pad_left + 35, pad_top + 50), (pad_right - 35, pad_top + 60)], radius=4, fill=line_color)
    draw.rounded_rectangle([(pad_left + 35, pad_top + 90), (pad_right - 35, pad_top + 100)], radius=4, fill=line_color)
    draw.rounded_rectangle([(pad_left + 35, pad_top + 130), (pad_right - 100, pad_top + 140)], radius=4, fill=line_color)

    # 5. 导出为完美的 Windows .ico 复合图标文件
    # 包含 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 全尺寸
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(output_path, format="ICO", sizes=icon_sizes)
    print(f"Success: Icon file generated successfully at {output_path}")

if __name__ == "__main__":
    generate_blue_app_icon()
