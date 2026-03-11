#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
import subprocess
from pathlib import Path

def install_dependencies():
    """自动检测并安装依赖"""
    print("正在检查依赖...")
    
    # 需要安装的依赖
    dependencies = [
        'rawpy',
        'pillow',
        'pillow-heif',
        'ffmpeg-python',
        'tqdm'
    ]
    
    # 检查并安装依赖
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✓ {dep} 已安装")
        except ImportError:
            print(f"✗ {dep} 未安装，正在安装...")
            try:
                # 添加 --break-system-packages 标志以绕过外部管理环境限制
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep, '--break-system-packages'])
                print(f"✓ {dep} 安装成功")
            except Exception as e:
                print(f"✗ 安装 {dep} 失败: {e}")
                return False
    
    # 检查ffmpeg命令行工具
    try:
        subprocess.check_output(['ffmpeg', '-version'], stderr=subprocess.STDOUT)
        print("✓ ffmpeg 已安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ ffmpeg 未安装")
        print("请安装ffmpeg命令行工具：")
        print("- macOS: brew install ffmpeg")
        print("- Ubuntu: apt-get install ffmpeg")
        print("- Windows: 从官网下载并安装")
        return False
    
    return True

# 自动安装依赖
if not install_dependencies():
    print("依赖安装失败，程序将中止")
    sys.exit(1)

# 导入必要的库
import rawpy
from PIL import Image
import pillow_heif
import ffmpeg
from tqdm import tqdm

# 初始化pillow-heif
pillow_heif.register_heif_opener()

# 支持的图片格式（包括raw格式）
IMAGE_EXTS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.nef', '.arw', '.cr2', '.cr3', '.dng', '.raf', '.pef',
    '.orf', '.sr2', '.mrw', '.rw2', '.x3f', '.hif'
}

# 支持的视频格式
VIDEO_EXTS = {
    '.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm'
}

def is_empty_directory(path):
    """检查目录是否为空"""
    if not os.path.isdir(path):
        return False
    return len(os.listdir(path)) == 0

def resize_image(img, max_pixels=2000000):
    """调整图片尺寸，确保不超过指定像素数"""
    width, height = img.size
    current_pixels = width * height
    
    if current_pixels <= max_pixels:
        return img
    
    # 计算新尺寸
    ratio = (max_pixels / current_pixels) ** 0.5
    new_width = int(width * ratio)
    new_height = int(height * ratio)
    
    # 调整尺寸
    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
    return resized_img

def convert_image_to_heif(input_path, output_path):
    """将图片转换为HEIF格式"""
    try:
        # 检查是否是RAW格式
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ['.nef', '.arw', '.cr2', '.cr3', '.dng', '.raf', '.pef', '.orf', '.sr2', '.mrw', '.rw2', '.x3f']:
            # 使用rawpy处理RAW文件
            with rawpy.imread(input_path) as raw:
                rgb = raw.postprocess()
            img = Image.fromarray(rgb)
        else:
            # 处理普通图片
            img = Image.open(input_path)
        
        # 调整图片尺寸到200万像素
        img = resize_image(img, max_pixels=2000000)
        
        # 转换为HEIF格式
        output_path = os.path.splitext(output_path)[0] + '.heif'
        img.save(output_path, format='HEIF', quality=75)
        return True
    except Exception as e:
        print(f"转换图片失败 {input_path}: {e}")
        return False

def convert_video_to_h264(input_path, output_path):
    """将视频转换为H.264编码的720p MP4格式"""
    try:
        output_path = os.path.splitext(output_path)[0] + '.mp4'
        
        # 使用subprocess直接调用ffmpeg命令，使用H.264编码以提高兼容性
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', 'scale=1280:720',
            '-vcodec', 'libx264',  # 使用H.264编码
            '-b:v', '1M',  # 将码率改为1Mbps
            '-preset', 'medium',
            '-profile:v', 'high10',  # 使用high10 profile支持10位深度
            '-level:v', '4.0',  # 适当的level设置
            '-acodec', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-threads', '4',  # 使用多线程加速
            '-y',  # 覆盖输出文件
            output_path
        ]
        
        # 运行命令，将输出重定向到 DEVNULL 以保持进度条显示
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"转换视频失败 {input_path}: {e}")
        return False

def process_directory(input_dir, output_dir):
    """处理目录中的所有文件"""
    # 首先计算总文件数、分别的视频和照片数量，以及文件大小
    total_files = 0
    total_images = 0
    total_videos = 0
    total_size = 0
    image_size = 0
    video_size = 0
    media_files = []
    
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            input_file = os.path.join(root, file)
            try:
                file_size = os.path.getsize(input_file)
            except:
                file_size = 0
            
            if ext in IMAGE_EXTS:
                total_files += 1
                total_images += 1
                total_size += file_size
                image_size += file_size
                media_files.append((root, file, 'image', file_size))
            elif ext in VIDEO_EXTS:
                total_files += 1
                total_videos += 1
                total_size += file_size
                video_size += file_size
                media_files.append((root, file, 'video', file_size))
    
    processed_files = 0
    processed_images = 0
    processed_videos = 0
    processed_size = 0
    failed_files = 0
    
    # 计算平均处理速度（基于文件大小）
    import time
    start_time = time.time()
    
    # 使用tqdm创建进度条，确保原地更新
    with tqdm(total=total_files, desc="处理进度", unit="文件", ncols=120, leave=True) as pbar:
        # 处理每个媒体文件
        for root, file, media_type, file_size in media_files:
            # 计算相对路径
            rel_path = os.path.relpath(root, input_dir)
            if rel_path == '.':
                rel_path = ''
            
            # 创建对应的输出目录
            output_subdir = os.path.join(output_dir, rel_path)
            os.makedirs(output_subdir, exist_ok=True)
            
            input_file = os.path.join(root, file)
            output_file = os.path.join(output_subdir, file)
            ext = os.path.splitext(file)[1].lower()
            
            # 处理视频时改变进度条颜色并显示提示
            if media_type == 'video':
                # 改变进度条颜色为蓝色
                if pbar.colour != 'blue':
                    pbar.colour = 'blue'
                    # 显示处理视频的提示
                    pbar.set_description("处理进度 (正在处理视频，用时会比照片久很多)")
            else:
                # 处理照片时恢复白色
                if pbar.colour != 'white':
                    pbar.colour = 'white'
                    pbar.set_description("处理进度")
            
            # 处理文件
            if media_type == 'image':
                # 处理图片
                if convert_image_to_heif(input_file, output_file):
                    processed_files += 1
                    processed_images += 1
                    processed_size += file_size
                else:
                    failed_files += 1
            elif media_type == 'video':
                # 处理视频
                if convert_video_to_h264(input_file, output_file):
                    processed_files += 1
                    processed_videos += 1
                    processed_size += file_size
                else:
                    failed_files += 1
            
            # 计算剩余时间
            elapsed_time = time.time() - start_time
            if processed_size > 0:
                # 基于已处理的大小和时间，估算剩余时间
                processing_rate = processed_size / elapsed_time
                remaining_size = total_size - processed_size
                estimated_remaining = remaining_size / processing_rate if processing_rate > 0 else 0
                
                # 转换为时分秒
                hours = int(estimated_remaining // 3600)
                minutes = int((estimated_remaining % 3600) // 60)
                seconds = int(estimated_remaining % 60)
                
                # 格式化剩余时间
                if hours > 0:
                    remaining_time_str = f"{hours}小时{minutes}分钟{seconds}秒"
                elif minutes > 0:
                    remaining_time_str = f"{minutes}分钟{seconds}秒"
                else:
                    remaining_time_str = f"{seconds}秒"
            else:
                remaining_time_str = "计算中..."
            
            # 更新进度条，显示详细信息
            pbar.set_postfix_str(f"已处理: {processed_files}/{total_files} | 照片: {processed_images}/{total_images} | 视频: {processed_videos}/{total_videos} | 预计剩余时间: {remaining_time_str}")
            pbar.update(1)
    
    return total_files, total_images, total_videos, processed_files, failed_files

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PLzipper - 压缩个人图库')
    parser.add_argument('input_dir', help='输入文件夹路径', nargs='?')
    parser.add_argument('output_dir', help='输出文件夹路径', nargs='?')
    
    args = parser.parse_args()
    
    # 如果没有提供命令行参数，交互式输入
    if not args.input_dir or not args.output_dir:
        print("PLzipper - 压缩个人图库")
        print("=" * 40)
        args.input_dir = input("请输入输入文件夹路径: ").strip()
        args.output_dir = input("请输入输出文件夹路径: ").strip()
    else:
        # 去除命令行参数中的空格
        args.input_dir = args.input_dir.strip()
        args.output_dir = args.output_dir.strip()
    
    # 检查输入目录是否存在
    if not os.path.isdir(args.input_dir):
        print(f"错误：输入目录不存在: {args.input_dir}")
        sys.exit(1)
    
    # 统计输入目录内的文件数量
    try:
        file_count = 0
        media_count = 0
        for root, dirs, files in os.walk(args.input_dir):
            file_count += len(files)
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                    media_count += 1
        print("\n\033[1;32m输入目录统计：\033[0m")
        print(f"\033[1;32m总文件数: {file_count}\033[0m")
        print(f"\033[1;32m媒体文件数: {media_count}\033[0m")
    except Exception as e:
        print(f"错误：无法访问输入目录: {e}")
        sys.exit(1)
    
    # 显示目录信息
    print(f"\033[1;32m待处理：{args.input_dir}\033[0m")
    print(f"\033[1;32m目标位置：{args.output_dir}\033[0m")
    print("\033[1;32m请确认。\033[0m")
    
    # 检查输出目录
    output_dir_empty = True
    if os.path.exists(args.output_dir):
        if not is_empty_directory(args.output_dir):
            output_dir_empty = False
            print("\033[1;31m检测到输出目录不是空目录\033[0m")
            # 使用红色粗体显示确认语句
            print("\033[1;31m⚠️  注意：此操作将删除输出目录中的所有文件和子目录！\033[0m")
            user_input = input("请确认是否清空输出目录？是请输入yes，否请输入任意字符: ")
            if user_input.lower() == 'yes':
                # 清空输出目录
                for root, dirs, files in os.walk(args.output_dir, topdown=False):
                    for file in files:
                        os.remove(os.path.join(root, file))
                    for dir in dirs:
                        os.rmdir(os.path.join(root, dir))
                print("\033[1;32m输出目录已清空\033[0m")
            else:
                print("\033[1;32m程序将中止\033[0m")
                sys.exit(1)
    else:
        # 创建输出目录
        os.makedirs(args.output_dir, exist_ok=True)
        print("\033[1;34m检测到输出目录是新创建的空目录\033[0m")
    
    if output_dir_empty:
        print("\033[1;34m检测到输出目录是空目录\033[0m")
    
    # 二次确认：生成示例文件
    print(f"\n生成示例文件...")
    print("正在复制目录结构并生成示例文件...")
    
    # 复制目录结构并生成示例文件
    sample_generated = False
    for root, dirs, files in os.walk(args.input_dir):
        # 计算相对路径
        rel_path = os.path.relpath(root, args.input_dir)
        if rel_path == '.':
            rel_path = ''
        
        # 创建对应的输出目录
        output_subdir = os.path.join(args.output_dir, rel_path)
        os.makedirs(output_subdir, exist_ok=True)
        
        # 按文件名排序
        sorted_files = sorted(files)
        
        # 找到第一个媒体文件
        for file in sorted_files:
            input_file = os.path.join(root, file)
            output_file = os.path.join(output_subdir, file)
            ext = os.path.splitext(file)[1].lower()
            
            if ext in IMAGE_EXTS:
                # 处理第一个图片
                if convert_image_to_heif(input_file, output_file):
                    print(f"生成示例图片: {input_file} -> {output_file}")
                    sample_generated = True
                break
            elif ext in VIDEO_EXTS:
                # 处理第一个视频
                if convert_video_to_h264(input_file, output_file):
                    print(f"生成示例视频: {input_file} -> {output_file}")
                    sample_generated = True
                break
    
    if sample_generated:
        print("\n已生成示例文件，请检查是否正确")
        user_input = input("检查完后请按Enter键开始处理所有文件，输入任意字符中止: ")
        if user_input.strip() != '':
            print("程序将中止")
            sys.exit(1)
    else:
        print("未找到媒体文件，程序将中止")
        sys.exit(1)
    
    print(f"\n开始处理所有照片...")
    print(f"输入目录: {args.input_dir}")
    print(f"输出目录: {args.output_dir}")
    print("将在示例文件的基础上继续处理剩余文件...")
    
    # 处理目录
    total, total_images, total_videos, processed, failed = process_directory(args.input_dir, args.output_dir)
    
    # 输出结果
    print(f"\n处理完成！")
    print(f"总文件数: {total}")
    print(f"照片数量: {total_images}")
    print(f"视频数量: {total_videos}")
    print(f"成功处理: {processed}")
    print(f"处理失败: {failed}")

if __name__ == '__main__':
    main()
