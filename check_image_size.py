#!/usr/bin/env python3
import os
from PIL import Image
import pillow_heif

# 初始化pillow-heif
pillow_heif.register_heif_opener()

def check_image_size(directory):
    """检查目录中所有HEIF图片的尺寸"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.heif'):
                file_path = os.path.join(root, file)
                try:
                    img = Image.open(file_path)
                    width, height = img.size
                    pixels = width * height
                    print(f"{file_path}: {width}x{height} = {pixels} pixels")
                    if pixels > 2000000:
                        print(f"  WARNING: 超过200万像素！")
                except Exception as e:
                    print(f"无法读取 {file_path}: {e}")

if __name__ == '__main__':
    check_image_size('./test/out')
