
import os
from pytube import YouTube
from pytube import Search
from collections import deque
import asyncio
import subprocess
import threading
import time
import signal
import random
from dotenv import load_dotenv
from highrise import BaseBot
from highrise.__main__ import BotDefinition
from highrise import *
from highrise import BaseBot, __main__, CurrencyItem, Item, Position, AnchorPosition, SessionMetadata, User

ICECAST_HOST = "link.zeno.fm"
ICECAST_PORT = "80"
ICECAST_USER = "source"
ICECAST_PASSWORD = "tXOQ2HbL"
ICECAST_MOUNT= "gpo09g38vpkvv"
ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASSWORD}@{ICECAST_HOST}:{ICECAST_PORT}/{ICECAST_MOUNT.strip()}"

SONG_QUEUE = deque()
current_process = None
current_song = None
queue_lock = asyncio.Lock()

class Bot(BaseBot):
    def __init__(self):
        super().__init__()

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        # بدء تشغيل أغنية عشوائية
        await add_random_song(asyncio.get_event_loop())

    async def on_chat(self, user: User, message: str) -> None:
        if message.startswith("-") and user.username=="Q._14":
            response = await self.command_handler(user.id, message)
            await self.highrise.chat(str(response))
        elif message.startswith("-") and user.username != "Q._14":
            await self.highrise.chat("ليس لديك صلاحيات التحكم في البوت")

    async def command_handler(self, user_id, message: str):
        help_msg = "🎵 الأوامر: \n-play [name] \n-skip \n -stop \n -queue \n-remove [id] \n -playnow [name] "

        if message.strip().lower() == "-help":
            return help_msg

        cmd_map = {
            "-play": ("play", 6),
            "-skip": ("skip", None),
            "-stop": ("stop", None),
            "-queue": ("queue", None),
            "-remove": ("remove", 8),
            "-playnow": ("playnow", 9)
        }

        for prefix, (cmd, cut) in cmd_map.items():
            if message.startswith(prefix):
                try:
                    arg = message[cut:].strip() if cut else ""
                    return await self.execute_command(cmd, arg)
                except Exception as e:
                    return f"⚠️ خطأ: {e}"
        return "⚠️ أمر غير معروف! اكتب -help"

    async def execute_command(self, command: str, arg: str):
        loop = asyncio.get_event_loop()
        if command == "play":
            await self.highrise.chat(f"🔎جاري البحث عنها ...")
            return await do_play(arg, loop)
        elif command == "playnow":
            return await do_play(arg, loop, immediate=True)
        elif command == "skip":
            return await do_skip()
        elif command == "stop":
            return await do_stop()
        elif command == "queue":
            return await do_queue()
        elif command == "remove":
            try:
                return await do_remove(int(arg))
            except:
                return "الرجاء إدخال رقم صحيح"
        return "أمر غير معروف"

async def stream_next_song(loop):
    global current_process, current_song
    await asyncio.sleep(0.3)

    async with queue_lock:
        if current_process is not None:
            return

        if not SONG_QUEUE:
            await add_random_song(loop)

        if not SONG_QUEUE:
            return

        current_song = SONG_QUEUE.popleft()
        audio_url, title = current_song
        print(f"Now playing: {title}")

        ffmpeg_command = [
            "ffmpeg",
            "-re",
            "-i", audio_url,
            "-acodec", "libmp3lame",
            "-ab", "128k",
            "-f", "mp3",
            ICECAST_URL
        ]

        proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        current_process = proc

        def wait_and_continue():
            global current_process, current_song
            proc.wait()
            current_process = None
            current_song = None
            time.sleep(0.5)

            if not SONG_QUEUE:
                queries = ["random music", "pop songs", "latest hits", "trending music", "اغاني اجنبية جديدة"]
                random_query = random.choice(queries)
                future = asyncio.run_coroutine_threadsafe(
                    do_play(random_query, loop, immediate=True), loop
                )
                try:
                    future.result(timeout=10)
                except Exception as e:
                    print(f"Failed to add random song: {e}")

            asyncio.run_coroutine_threadsafe(stream_next_song(loop), loop).result()

        threading.Thread(target=wait_and_continue, daemon=True).start()

async def add_random_song(loop):
    queries = ["random music", "pop songs", "latest hits", "trending music"]
    random_query = random.choice(queries)
    await do_play(random_query, loop, immediate=True)


async def do_play(song_query: str, loop, immediate=False) -> str:
    try:
        # البحث عن الفيديو باستخدام pytube
        s = Search(song_query)
        results = s.results
        if not results:
            return "لم يتم العثور على نتائج"

        # اختيار أول نتيجة
        yt = results[0]
        title = yt.title

        # استخراج رابط الصوت
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            return "لا يوجد تدفق صوتي متاح"

        audio_url = audio_stream.url

        # إضافة إلى الطابور
        async with queue_lock:
            if immediate:
                SONG_QUEUE.appendleft((audio_url, title))
            else:
                SONG_QUEUE.append((audio_url, title))

        response = f"تمت الإضافة إلى قائمة الانتظار: {title}"

        # بدء التشغيل إذا لم يكن هناك شيء يعمل
        if current_process is None:
            await stream_next_song(loop)
        elif immediate:
            current_process.send_signal(signal.SIGINT)

        return response

    except Exception as e:
        return f"خطأ: {str(e)}"
async def do_play22(song_query: str, loop, immediate=False) -> str:
    ydl_options = {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        query = "ytsearch1:" + song_query
        results = await search_ytdlp_async(query, ydl_options)
        tracks = results.get("entries", [])

        if not tracks:
            return "No results found."

        first_track = tracks[0]
        audio_url = first_track["url"]
        title = first_track.get("title", "Untitled")

        async with queue_lock:
            if immediate:
                SONG_QUEUE.appendleft((audio_url, title))
            else:
                SONG_QUEUE.append((audio_url, title))

        response = f"Added to queue: {title}"

        if current_process is None:
            await stream_next_song(loop)
        elif immediate:
            current_process.send_signal(signal.SIGINT)

        return response
    except Exception as e:
        return f"Error: {str(e)}"

async def do_skip() -> str:
    global current_process
    if current_process is not None:
        current_process.send_signal(signal.SIGINT)
        return "Skipping..."
    return "Nothing playing."

async def do_stop() -> str:
    global current_process, current_song
    async with queue_lock:
        if current_process is not None:
            current_process.kill()
            current_process = None

        SONG_QUEUE.clear()
        current_song = None
    return "Stopped and cleared queue."

async def do_queue() -> str:
    message = []
    async with queue_lock:
        if current_song:
            message.append(f"Now Playing: {current_song[1]}")
        else:
            message.append("Nothing playing.")

        if SONG_QUEUE:
            message.append("\nQueue:")
            for idx, (url, title) in enumerate(SONG_QUEUE, start=1):
                message.append(f"{idx}. {title}")
        else:
            message.append("\nQueue is empty.")
    return "\n".join(message)

async def do_remove(position: int) -> str:
    async with queue_lock:
        if position < 1 or position > len(SONG_QUEUE):
            return "Invalid position."

        removed_song = SONG_QUEUE[position-1]
        del SONG_QUEUE[position-1]
        return f"Removed: {removed_song[1]}"

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)
