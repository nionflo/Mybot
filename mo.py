import os
import pytube
import asyncio
import subprocess
import threading
import time
import signal
import random
from collections import deque
from dotenv import load_dotenv
from highrise import BaseBot
from highrise.__main__ import BotDefinition
from highrise import *
from highrise import BaseBot, __main__, CurrencyItem, Item, Position, AnchorPosition, SessionMetadata, User
from youtubesearchpython import VideosSearch

# إعدادات Icecast
ICECAST_HOST = "link.zeno.fm"
ICECAST_PORT = "80"
ICECAST_USER = "source"
ICECAST_PASSWORD = "tXOQ2HbL"
ICECAST_MOUNT= "gpo09g38vpkvv"
ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASSWORD}@{ICECAST_HOST}:{ICECAST_PORT}/{ICECAST_MOUNT.strip()}"

# المتغيرات العامة
SONG_QUEUE = deque()
current_process = None
current_song = None
queue_lock = asyncio.Lock()

class Bot(BaseBot):
    def __init__(self):
        super().__init__()

    async def on_start(self, session_metadata: SessionMetadata) -> None:
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
            await self.highrise.chat(f"🔎 جاري البحث...")
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
        # البحث باستخدام youtube-search-python
        search = VideosSearch(song_query, limit=1)
        results = search.result()["result"]
        
        if not results:
            return "لم يتم العثور على نتائج"

        # استخراج معلومات الفيديو
        video_id = results[0]["id"]
        video_url = f"https://youtu.be/{video_id}"
        title = results[0]["title"]

        # استخراج رابط الصوت باستخدام pytube
        yt = pytube.YouTube(video_url)
        audio_stream = yt.streams.get_audio_only()
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

        if current_process is None:
            await stream_next_song(loop)
        elif immediate:
            current_process.send_signal(signal.SIGINT)

        return response

    except Exception as e:
        return f"خطأ: {str(e)}"

async def do_skip() -> str:
    global current_process
    if current_process is not None:
        current_process.send_signal(signal.SIGINT)
        return "جاري التخطي..."
    return "لا يوجد شيء يعمل حاليًا"

async def do_stop() -> str:
    global current_process, current_song
    async with queue_lock:
        if current_process is not None:
            current_process.kill()
            current_process = None

        SONG_QUEUE.clear()
        current_song = None
    return "تم الإيقاف وتفريغ القائمة"

async def do_queue() -> str:
    message = []
    async with queue_lock:
        if current_song:
            message.append(f"الآن يعمل: {current_song[1]}")
        else:
            message.append("لا يوجد شيء يعمل حاليًا.")

        if SONG_QUEUE:
            message.append("\nقائمة الانتظار:")
            for idx, (url, title) in enumerate(SONG_QUEUE, start=1):
                message.append(f"{idx}. {title}")
        else:
            message.append("\nقائمة الانتظار فارغة.")
    return "\n".join(message)

async def do_remove(position: int) -> str:
    async with queue_lock:
        if position < 1 or position > len(SONG_QUEUE):
            return "رقم غير صالح"

        removed_song = SONG_QUEUE[position-1]
        del SONG_QUEUE[position-1]
        return f"تمت الإزالة: {removed_song[1]}"
