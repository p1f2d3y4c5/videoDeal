import os
import subprocess
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sys
# copy_video 函数和 compress_video 函数： 在这两个函数中使用了 tqdm 来显示进度条，并确保进度条可以正确地更新。
# copy_or_compress_video 函数： 根据视频的比特率决定是调用 compress_video 函数进行压缩，还是调用 copy_video 函数进行复制，并传递进度条对象以便更新。
# process_videos 函数： 使用 ThreadPoolExecutor 来并发处理多个视频文件，同时确保每个视频的处理过程都能正确地显示进度条。
# 检查是否有NVIDIA显卡支持FFmpeg
def check_gpu_support():
    result = subprocess.run(["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True)
    return "cuda" in result.stdout.decode().lower()

# 获取视频总时长（秒）
def get_video_duration(input_file):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

# 获取视频比特率（kbps）
def get_video_bitrate(input_file):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=bit_rate", "-of", "default=noprint_wrappers=1:nokey=1", input_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip()) / 1000  # 转换为kbps

# 复制视频并显示进度条
def copy_video(input_file, output_file, pbar=None):
    cmd = ["ffmpeg", "-i", input_file, "-c", "copy", output_file]
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')

    total_duration = get_video_duration(input_file)
    progress = tqdm(total=total_duration, desc=f"Copying and converting to MP4 {os.path.basename(input_file)}", unit="s", leave=False, position=1)

    while True:
        line = process.stderr.readline()
        if not line:
            break
        if "time=" in line:
            time_match = re.search(r"time=(\d+:\d+:\d+.\d+)", line)
            if time_match:
                time_str = time_match.group(1)
                h, m, s = map(float, time_str.split(':'))
                current_time = h * 3600 + m * 60 + s
                progress.update(current_time - progress.n)
                progress.set_description(f"Processing time: {time_str}")
                progress.refresh()  # 刷新进度条
    progress.close()
    process.communicate()
    if pbar:
        pbar.update(1)

# 压缩视频并显示进度条
def compress_video(input_file, output_file, use_gpu=False, pbar=None):
    encoder = "h264_nvenc" if use_gpu else "libx264"
    cmd = ["ffmpeg", "-i", input_file, "-vf", "scale=-1:720", "-c:v", encoder, "-crf", "32", "-b:v", "1000k", output_file]
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', errors='ignore')

    total_duration = get_video_duration(input_file)
    progress = tqdm(total=total_duration, desc=f"Compressing {os.path.basename(input_file)}", unit="s", leave=False)

    while True:
        line = process.stderr.readline()
        if not line:
            break
        if "time=" in line:
            time_match = re.search(r"time=(\d+:\d+:\d+.\d+)", line)
            if time_match:
                time_str = time_match.group(1)
                h, m, s = map(float, time_str.split(':'))
                current_time = h * 3600 + m * 60 + s
                progress.update(current_time - progress.n)
                progress.set_description(f"Processing time: {time_str}")
                sys.stdout.flush()
    progress.close()
    process.communicate()
    if pbar:
        pbar.update(1)

# 复制视频为MP4格式或压缩视频，并显示进度条
def copy_or_compress_video(input_file, output_file, use_gpu=False, pbar=None):
    bitrate = get_video_bitrate(input_file)
    if bitrate <= 1000:
        print(f"文件 {os.path.basename(input_file)} 的比特率小于或等于1000k，所以不执行压缩，将其转换为MP4格式。")
        copy_video(input_file, output_file, pbar=pbar)
    else:
        compress_video(input_file, output_file, use_gpu=use_gpu, pbar=pbar)

# 获取指定文件夹下所有视频文件名
def get_all_files(directory, extensions=('.mp4', '.avi', '.mov', '.mkv', ".ts")):
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.lower().endswith(extensions):
                files.append(os.path.join(root, filename))
    return files

# 多线程视频处理函数
def process_videos(files, output_dir, use_gpu=False):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        with tqdm(total=len(files), desc="Processing videos") as pbar:
            for file in files:
                file = os.path.abspath(file)  # 确保输入文件是绝对路径
                output_file = os.path.join(output_dir, os.path.basename(os.path.splitext(file)[0] + "_s.mp4"))
                #output_file = os.path.join(output_dir, os.path.basename(os.path.splitext(file)[0] + "_s.mp4"))
                futures.append(executor.submit(copy_or_compress_video, file, output_file, use_gpu=use_gpu, pbar=pbar))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error processing file: {e}")

if __name__ == "__main__":
    ffmpeg_path = r"C:\userjin\app\ffmpeg\bin"
    os.environ["PATH"] += os.pathsep + ffmpeg_path

    input_dir = r"G:\森日_s\1"
    output_dir = r"G:\森日_s"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if check_gpu_support():
        print("NVIDIA显卡支持FFmpeg加速.")
        use_gpu = True
    else:
        print("没有检测到NVIDIA显卡，将使用CPU.")
        use_gpu = False

    files = get_all_files(input_dir)
    process_videos(files, output_dir, use_gpu)
