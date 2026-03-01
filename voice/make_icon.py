import subprocess, sys

# 确保 Pillow 已安装
subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])

from PIL import Image

src = r"c:\Users\11424\Desktop\新建文件夹\voice\logo.ico"   # 实际是 PNG
img = Image.open(src).convert("RGBA")
w, h = img.size
print(f"原尺寸: {w}x{h}")

# 从水平中心裁出正方形
size = h
left = (w - size) // 2
square = img.crop((left, 0, left + size, size))

# 生成标准多尺寸 ICO
ico_out = r"c:\Users\11424\Desktop\新建文件夹\voice\logo_fixed.ico"
square.save(ico_out, format="ICO",
            sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f"ICO saved: {ico_out}")

# 生成 256x256 PNG 供窗口图标用
png_out = r"c:\Users\11424\Desktop\新建文件夹\voice\logo.png"
square.resize((256, 256), Image.LANCZOS).save(png_out, format="PNG")
print(f"PNG saved: {png_out}")
print("完成！")
