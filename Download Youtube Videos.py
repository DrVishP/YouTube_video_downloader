from pytubefix import YouTube, Playlist
import os
import time
import re
from datetime import datetime, timezone, timedelta
from better_ffmpeg_progress import FfmpegProcess

file_size = 0
start_time = 0

def seconds_to_hms(seconds):
    return datetime.utcfromtimestamp(seconds).strftime('%H:%M:%S')

def sanitize_filename(name):
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned

def handle_temp_files(video_path, audio_path, save_location, safe_title, keep_temp_files):
    if keep_temp_files:
        new_video_path = os.path.join(save_location, f"{safe_title}.mp4")
        new_audio_path = os.path.join(save_location, f"{safe_title}.m4a")

        if os.path.exists(video_path):
            os.rename(video_path, new_video_path)
            print(f"🎞️ Renamed video to: {new_video_path}")

        if os.path.exists(audio_path):
            os.rename(audio_path, new_audio_path)
            print(f"🎵 Renamed audio to: {new_audio_path}")
    else:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)

def merge_video_audio(video_path, audio_path, output_path):
    try:
        print("🔀 Merging video and audio...")
        command = ["ffmpeg", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", output_path]
        process = FfmpegProcess(command)
        process.use_tqdm = False
        process.run()
        print("\n✅ Merged!")
        print(f"📁 Saved: {output_path}")
    except Exception as e:
        print(f"❌ Merge failed: {e}")

def on_progress(stream, chunk, bytes_remaining):
    global file_size, start_time
    bytes_downloaded = file_size - bytes_remaining
    percent = (bytes_downloaded / file_size) * 100
    elapsed = time.time() - start_time
    speed = bytes_downloaded / elapsed if elapsed > 0 else 0
    eta = (file_size - bytes_downloaded) / speed if speed > 0 else 0

    status = (f"{percent:1.1f}% | {bytes_downloaded / 1024 / 1024:.2f}MB of {file_size / 1024 / 1024:.2f}MB | "
              f"{speed / 1024 / 1024:.2f}MB/s | ETA: {eta:.1f}s")
    print(f"\r{status}", end='', flush=True)

def download_stream(stream, file_path):
    global file_size, start_time
    file_size = stream.filesize
    start_time = time.time()
    save_location, filename = os.path.split(file_path)
    stream.download(output_path=save_location, filename=filename)

def download_playlist(playlist_url, save_location):
    try:
        pl = Playlist(playlist_url)
        print(f"\n📃 Playlist: {pl.title}")
        print(f"🎞️ Found {len(pl.video_urls)} videos")

        for i, video_url in enumerate(pl.video_urls, 1):
            print(f"\n🔢 Downloading {i}/{len(pl.video_urls)}: {video_url}")
            download_with_resolution_choice(video_url, save_location)

    except Exception as e:
        print(f"\n❌ Playlist error: {e}")

def download_with_resolution_choice(link, save_location):
    try:
        yt = YouTube(link, on_progress_callback=on_progress)
        video_streams = yt.streams.filter(only_video=True, file_extension='mp4').order_by('resolution').desc()
        audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
        video_length = seconds_to_hms(yt.length)
        just_date = yt.publish_date.date()
        
        if not video_streams or not audio_stream:
            print("❌ No suitable streams found.")
            return

        print(f"\n🎬 Channel: {yt.author} | Published: {just_date} | Length: {video_length}")
        print(f"🎬 Title: {yt.title}")
        selected_video = None

        if auto_select:
            # Try exact match for both resolution and codec
            for stream in video_streams:
                codec = stream.codecs[0].split('.')[0] if stream.codecs else ""
                if stream.resolution == default_resolution and codec == default_codec:
                    selected_video = stream
                    break

            if not selected_video:
                # Try matching resolution only
                for stream in video_streams:
                    if stream.resolution == default_resolution:
                        selected_video = stream
                        break

            if not selected_video:
                # Pick highest available resolution
                selected_video = video_streams[0]
        else:
            # Manual selection fallback
            print("\n⚠️ No matching default found. Please choose manually:")
            for i, stream in enumerate(video_streams):
                codec = stream.codecs[0] if stream.codecs else "Unknown"
                print(f"{i + 1}. {stream.resolution} ({stream.fps}fps) | Codec: {codec} | Size: {stream.filesize/1024/1024:.2f} MB")
            choice = int(input("👉 Enter the number of your preferred stream: ")) - 1
            selected_video = video_streams[choice]

        print(f"🎥 {selected_video.resolution} | 🎛️ Codec: {selected_video.codecs[0]} | 🔊 {audio_stream.abr}")
        codec_short = selected_video.codecs[0].split('.')[0] if selected_video.codecs else "unknown"
        safe_title = sanitize_filename(yt.title)
        
        temp_filename = datetime.now().strftime("%Y-%m-%d - %H;%M;%S") + " Temp"
        
        print("\n⬇️ Downloading video stream as Temp.mp4...")
        video_path = os.path.join(temp_location, f"{temp_filename}.mp4")
        download_stream(selected_video, video_path)

        print("\n⬇️ Downloading audio stream as Temp.m4a...")
        audio_path = os.path.join(temp_location, f"{temp_filename}.m4a")
        download_stream(audio_stream, audio_path)

        print("\n🎉 Done! Temp files saved.")
        
        output_filename = f"{just_date}, {yt.author}, {safe_title} ({selected_video.resolution} {codec_short}).mp4"
        output_path = os.path.join(save_location, output_filename)

        merge_video_audio(video_path, audio_path, output_path)
        handle_temp_files(video_path, audio_path, save_location, safe_title, keep_temp_files)

    except Exception as e:
        print(f"\n❌ Error: {e}")

# Add this to your global user settings
keep_temp_files = False
auto_select = True
default_resolution = "1080p"
default_codec = "av01"
temp_location = r"C:\Temp"
save_location = r"C:\YouTube"

input_links = input("📋 Enter YouTube video or playlist URLs separated by commas:\n").split(',')

for url in input_links:
    cleaned_url = url.strip()
    if "playlist" in cleaned_url:
        download_playlist(cleaned_url, save_location)
    elif cleaned_url:
        download_with_resolution_choice(cleaned_url, save_location)