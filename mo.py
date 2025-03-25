from highrise import BaseBot, __main__, CurrencyItem, Item, Position, AnchorPosition, SessionMetadata, User, ResponseError
from highrise.__main__ import BotDefinition
from asyncio import run as arun, Lock, create_task
import asyncio
import os
import aiofiles
from typing import List, Dict
from highrise.webapi import *
import random
import aiohttp
from dataclasses import dataclass, asdict
import json

# أسماء ملفات تخزين بيانات المشرفين والمصممين
ADMINS_FILE = "admins.txt"
DESIGNERS_FILE = "designers.txt"

class Bot(BaseBot):
    def __init__(self):
        super().__init__()
        self.bot_position = Position(16.5, 12.5, 11.0, "FrontRight")
        self.me = "1_on_1:67def926832b9b432ba573b4:67e04bad95052fea8e922cb4"
        self.bot_id = None
        self.pinned_users = {}
        self.anchored_players: Dict[str, Position] = {}
        self.saved_positions: Dict[str, Position] = {}
        self.anchor_lock = Lock()
        self.muted_players: set = set()
        self.emotes_list: List[str] = []
        self.active_loops: Dict[str, bool] = {}
        self.loop_tasks: Dict[str, asyncio.Task] = {}
        self.file_lock = asyncio.Lock()
        self.emotes_file = "emo.txt"
        # القوائم التي سيتم تحميلها من الملفات
        self.admin_list: List[str] = []
        self.designer_list: List[str] = []
        # عبارات الترحيب
        self.wlc_msg = [
            "👽 {user.username} وصل من كوكب زولتان يطلب أسياخ شاورما!",
            "🦄 وحيد قرن سحري اسمه {user.username} انضم إلينا!",
            "🧟 {user.username} خرج من القبر عشان يشوف حفلة الروم!",
            "🐓 {user.username} دخل وراح يربح معركة الديوك الحلقة الجديدة!",
            "🦴 آهلاً {user.username}، هل أتيت بحثاً عن عظمة البوت المفقودة؟",
            "🪓 {user.username} جاي يقطع البالونة قبل ما تطير!",
            "🎨 {user.username} حمل فرشاته وجاي يرسم لوحة في الهواء!",
            "🚀 {user.username} هبط بمركبته الفضائية عند الباب الأمامي!",
            "🧙♂️ الساحر {user.username} حول التراب إلى ذهب في الروم!",
            "⚡ {user.username} يجلب طاقة زي 'آينشتاين' بعد القهوة!",
            "🎬 {user.username} دخل بدراجة مثل فيلم E.T. الكلاسيكي!",
            "🍕 {user.username} جاي يوزع بيتزا مجانية على كل الحضور!",
            "🕵️♂️ تم رصد {user.username} يختبئ خلف الأريكة!",
            "🎲 {user.username} رمى النرد وحصل على بطاقة دخول ذهبية!",
            "🎪 {user.username} افتتح سيرك البوت الرقمي!",
            "🦥 {user.username} وصل بسرعة سلحفاة لكنه جاي!",
            "🍩 {user.username} يجلب صندوق دونات سحري للجميع!",
            "🧲 {user.username} جذب الكرسي الذكي بالماغناطيس!"
        ]


    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        try:
            conversation = await self.highrise.get_messages(conversation_id)
            message = conversation.messages[0].content
            print(conversation_id)
            # await self.highrise.send_message(conversation_id, response)
        except Exception as e:
            error_msg = f"حدث خطأ في المعالجة: {str(e)}"
            await self.highrise.send_message(conversation_id, error_msg)

    async def load_list_from_file(self, filename: str) -> List[str]:
        items = []
        if not os.path.exists(filename):
            # إنشاء الملف إن لم يكن موجوداً
            async with aiofiles.open(filename, "w") as f:
                await f.write("")
        async with aiofiles.open(filename, "r") as f:
            lines = await f.readlines()
            for line in lines:
                name = line.strip()
                if name:
                    items.append(name)
        return items

    async def save_list_to_file(self, filename: str, items: List[str]):
        async with aiofiles.open(filename, "w") as f:
            await f.write("\n".join(items))

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        self.bot_id = session_metadata.user_id
        await self.highrise.teleport(self.bot_id, self.bot_position)
        await self.load_emotes_from_file()
        # تحميل المشرفين والمصممين من الملفات
        self.admin_list = await self.load_list_from_file(ADMINS_FILE)
        self.designer_list = await self.load_list_from_file(DESIGNERS_FILE)
        print(f"تم تحميل {len(self.admin_list)} مشرف و {len(self.designer_list)} مصمم.")

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        random_msg = random.choice(self.wlc_msg)
        formatted_msg = random_msg.format(user=user)
        await self.highrise.chat(formatted_msg)

    async def handle_emote_error(self, user_id: str, index: int, error: Exception):
        if isinstance(error, ResponseError):
            if "Emote is not free or owned by target user" in str(error):
                await self.remove_invalid_emote(index)
                msg = "❌ هذه الرقصة غير متاحة وتم حذفها من القائمة"
            else:
                msg = f"⚠️ خطأ في الإرسال: {str(error)}"
        else:
            msg = f"🚨 خطأ غير متوقع: {str(error)}"
        # await self.highrise.whisper(user_id, msg)

    async def load_emotes_from_file(self):
        try:
            async with self.file_lock:
                async with aiofiles.open(self.emotes_file, "r") as f:
                    lines = await f.readlines()
                    self.emotes_list = [line.strip() for line in lines if ':' in line]
                    print(f"تم تحميل {len(self.emotes_list)} رقصة بنجاح")
        except FileNotFoundError:
            print("لم يتم العثور على ملف الرقصات، سيتم إنشاؤه تلقائيًا")
            async with aiofiles.open(self.emotes_file, "w") as f:
                await f.write("")

    async def save_emotes_to_file(self):
        async with self.file_lock:
            async with aiofiles.open(self.emotes_file, "w") as f:
                await f.write("\n".join(self.emotes_list))

    async def remove_invalid_emote(self, index: int):
        if 0 <= index < len(self.emotes_list):
            removed_emote = self.emotes_list.pop(index)
            await self.save_emotes_to_file()
            print(f"تم حذف الرقصة غير الصالحة: {removed_emote}")

    async def loop_emote(self, user_id: str, emote_id: str, duration: float, original_index: int):
        while self.active_loops.get(user_id, False):
            try:
                await self.highrise.send_emote(emote_id, user_id)
                await asyncio.sleep(duration)
            except ResponseError as e:
                if "Emote is not free or owned by target user" in str(e):
                    # await self.highrise.whisper(user_id, "❌ الرقصة غير متاحة!")
                    await self.remove_invalid_emote(original_index)
                    await self.stop_loop(user_id)
                    break
                else:
#                    await self.highrise.whisper(user_id, f"⚠ خطأ: {str(e)}")
                    break
            except Exception as e:
                print(f"خطأ غير متوقع: {str(e)}")
                await self.stop_loop(user_id)
                break

    async def start_loop(self, user_id: str, index: int):
        await self.stop_loop(user_id)
        if 0 <= index < len(self.emotes_list):
            try:
                emote_entry = self.emotes_list[index]
                if ':' not in emote_entry:
                    raise ValueError("تنسيق خاطئ")
                emote_id, duration_str = emote_entry.split(':')
                duration = float(duration_str)
                self.active_loops[user_id] = True
                task = asyncio.create_task(
                    self.loop_emote(user_id, emote_id, duration, index)
                )
                self.loop_tasks[user_id] = task
            except (ValueError, IndexError) as e:
                await self.remove_invalid_emote(index)
        else:
            return None

    async def background_task(self, func, *args, **kwargs):
        try:
            await func(*args, **kwargs)
        except Exception as e:
            print(f"Error in background task: {str(e)}")

    async def on_chat(self, user: User, message: str) -> None:
        # السماح باستخدام أوامر البوت (تبدأ بشرطة "-") للمشرفين والمصممين
        if message.startswith("-") and (user.username in self.admin_list or user.username in self.designer_list):
            create_task(self.background_task(self.process_command, user, message))
        elif message.lower().startswith("id @"):
            create_task(self.background_task(self.process_id_request, message))

        message2 = message.strip().lower()
 
        if message2 == "رقصني":
            if not self.emotes_list:
                await self.highrise.whisper(user.id, "⚠️ لا توجد رقصات متاحة حالياً")
                return
            try:
                random_emote = random.choice(self.emotes_list)
                emote_id, duration = random_emote.split(':')
                await self.highrise.send_emote(emote_id, user.id)
            except Exception as e:
                index = self.emotes_list.index(random_emote)
                await self.handle_emote_error(user.id, index, e)
            return
        elif message2 == 'توقف':
            await self.stop_loop(user.id)
            return
        elif message.isdigit():
            try:
                index = int(message) - 1
                if 0 <= index < len(self.emotes_list):
                    emote_id, duration = self.emotes_list[index].split(':')
                    await self.highrise.send_emote(emote_id, user.id)
                else:
                    await self.highrise.whisper(user.id, f"⚠️ الرقم يجب أن يكون بين 1 و {len(self.emotes_list)} {user.username}")
            except Exception as e:
                await self.handle_emote_error(user.id, index, e)
            return
        elif message2 == "صعدني":
            await self.highrise.teleport(user.id, Position(13.0, 12.5, 11.5))
        elif message2 == "نزلني":
            await self.highrise.teleport(user.id, Position(10.5, 0.0, 14.5))
        elif message.lower().startswith("loop "):
            parts = message.split()
            if len(parts) != 2 or not parts[1].isdigit():
                return
            index = int(parts[1]) - 1
            await self.start_loop(user.id, index)

    async def process_id_request(self, message: str):
        target_username = message.split("@")[1].strip().lower()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://webapi.highrise.game/users",
                params={"username": target_username}
            ) as resp:
                if resp.status != 200:
                    return await self.highrise.chat("⚠️ فشل في الاتصال بالسيرفر!")
                data = await resp.json()
                if not data.get("users") or data["total"] == 0:
                    return await self.highrise.chat("❌ المستخدم غير موجود!")
                user_id = data["users"][0]["user_id"]
                await self.highrise.chat(f"🆔 ID الخاص بـ {target_username}: {user_id}")

    async def handle_punishment(self, command: str, target_user: User, duration: str = None, is_designer: bool = False):
        try:
            # إذا كان الأمر كتم وكان المستخدم مصمم وليس مشرف، يتم فرض مدة نصف دقيقة فقط
            if command == "كتم" and is_designer:
                duration_sec = 30
            else:
                duration_sec = 300
                if duration:
                    if duration == "ساعه":
                        duration_sec = 3600
                    elif duration.isdigit():
                        duration_sec = int(duration) * 60
                    else:
                        return "⚠ المدة غير صالحة! استخدم رقمًا أو 'ساعه'"
            mt = duration_sec / 60
            if command == "كتم":
                await self.highrise.moderate_room(target_user.id, "mute", duration_sec)
                return f"تم كتم {target_user.username} لمدة {mt} دقيقة⏳"
            elif command == "باند":
                await self.highrise.moderate_room(target_user.id, "ban", duration_sec)
                return f"تم حظر {target_user.username} لمدة {mt} دقيقة ⛔"
            elif command == "طرد":
                await self.highrise.moderate_room(target_user.id, "kick")
                return f"تم طرد {target_user.username} بنجاح 🚪"
        except Exception as e:
            return f"❌ خطأ: {str(e)}"

    async def process_command(self, user: User, message: str):
        response = await self.command_handler(user, message)
        try:
            await self.highrise.chat(str(response))
        except Exception as e:
            print(f"إرسال فشل: {e}")

    async def command_handler(self, user: User, message: str):
        admin_help_msg = "⚙️ أوامر المشرف: طرد/كتم/باند [اسم+مدة] | ثبت/تحرير [اسم] | مشرف/لاعب/مصمم/حذف @اسم"
        designer_help_msg = "⚙️ أوامر المصمم: جيب/نقل/ابعد [اسم]"
        parts = message.split()
        if len(parts) < 2:
            if user.username in self.admin_list:
                return admin_help_msg
            elif user.username in self.designer_list:
                return designer_help_msg
            else:
                return "⚠️ ليس لديك صلاحية لاستخدام هذه الأوامر."

        command = parts[0]
        target_username = parts[1].replace("@", "") if parts[1].startswith("@") else parts[1]

        # الحصول على قائمة مستخدمي الغرفة
        try:
            room_users = await self.highrise.get_room_users()
            user_dict = {u.username: (u.id, u) for u, _ in room_users.content}
        except Exception as e:
            return f"❌ فشل الحصول على مستخدمي الغرفة: {str(e)}"

        # صلاحيات المستخدم
        is_admin = user.username in self.admin_list
        is_designer = user.username in self.designer_list

        # أوامر الإضافة والإزالة (للمشرفين فقط)
        if command == "-مشرف" and is_admin:
            if target_username in self.admin_list:
                return f"{target_username} موجود مسبقًا ضمن المشرفين."
            self.admin_list.append(target_username)
            await self.save_list_to_file(ADMINS_FILE, self.admin_list)
            await self.highrise.send_message(self.me, f"@{user.username} من قبل  {message}")
            return f"تم إضافة {target_username} إلى قائمة المشرفين."
        if command == "-لاعب" and is_admin:
            if target_username not in self.admin_list:
                return f"{target_username} غير موجود في قائمة المشرفين."
            self.admin_list.remove(target_username)
            await self.save_list_to_file(ADMINS_FILE, self.admin_list)
            await self.highrise.send_message(self.me, f"@{user.username} من قبل {message}")
            return f"تم إزالة {target_username} من قائمة المشرفين."
        if command == "-مصمم" and is_admin:
            if target_username in self.designer_list:
                return f"{target_username} موجود مسبقًا ضمن المصممين."
            self.designer_list.append(target_username)
            await self.save_list_to_file(DESIGNERS_FILE, self.designer_list)
            await self.highrise.send_message(self.me, f"@{user.username} من قبل  {message}")
            return f"تم إضافة {target_username} إلى قائمة المصممين."
        if command == "-حذف" and is_admin:
            if target_username not in self.designer_list:
                return f"{target_username} غير موجود في قائمة المصممين."
            self.designer_list.remove(target_username)
            await self.save_list_to_file(DESIGNERS_FILE, self.designer_list)
            await self.highrise.send_message(self.me, f"@{user.username} من قبل {message}")
            return f"تم إزالة {target_username} من قائمة المصممين."

        # أوامر العقوبات: يسمح للمشرفين بتنفيذ جميعها، بينما يُسمح للمصممين بكتم الشخص فقط (ولمدة نصف دقيقة)
        if command in ["-كتم", "-باند", "-طرد"]:
            if command in ["-باند", "-طرد"] and not is_admin:
                return "⚠️ هذه الأوامر مخصصة للمشرفين فقط."
            if command == "-كتم" and not (is_admin or is_designer):
                return "⚠️ هذه الأوامر مخصصة للمشرفين والمصممين فقط."
            if target_username in self.admin_list:
                return "لا يمكنك تنفيذ هذا الأمر على مشرف."
            if target_username not in user_dict:
                return "⚠️ هذا اللاعب غير موجود في الغرفة!"
            duration = parts[2] if len(parts) > 2 else None
            target_user = user_dict[target_username][1]
            is_designer_only = (command == "-كتم" and is_designer and not is_admin)
            return await self.handle_punishment(command[1:], target_user, duration, is_designer_only)

        # أوامر النقل والتحريك (متاحة للمشرفين والمصممين)
        if command in ["-نقل", "-جيب", "-ثبت", "-ابعد", "-تحرير", "-حرف", "-الوان", "-ازياء", "-vip", "-صعد"]:
            if target_username not in user_dict:
                return "⚠️ اللاعب غير موجود في الغرفة!"
            target_user = user_dict[target_username][1]
            if command == "-جيب":
                sender_pos = next((pos for u, pos in room_users.content if u.username == user.username), None)
                if not sender_pos:
                    return "⚠️ موقعك غير متوفر!"
                new_pos = Position(sender_pos.x + 1, sender_pos.y, sender_pos.z, sender_pos.facing)
                await self.highrise.teleport(target_user.id, new_pos)
                return f"تم إحضار {target_username} إليك 🚀"
            elif command == "-نقل":
                target_pos = next((pos for u, pos in room_users.content if u.username == target_username), None)
                if not target_pos:
                    return "⚠️ اللاعب غير موجود!"
                self.saved_positions[target_username] = target_pos
                sender = user_dict[user.username]
                await self.highrise.teleport(sender[0], target_pos)
                return f"تم النقل إلى {target_username} 📦"
            elif command == "-ثبت":
                admin_pos = next((pos for u, pos in room_users.content if u.username == user.username), None)
                if not admin_pos:
                    return "⚠️ موقعك غير متوفر!"
                self.pinned_users[target_user.id] = {
                    "username": target_username.lower(),
                    "admin_location": admin_pos,
                    "admin_username": user.username
                }
                await self.highrise.teleport(target_user.id, admin_pos)
                return f"تم تثبيت {target_username} في موقع {user.username} 📌"
            elif command == "-تحرير":
                target_username_lower = target_username.lower()
                target_id = None
                for uid, data in self.pinned_users.items():
                    if data["username"] == target_username_lower:
                        target_id = uid
                        break
                if target_id:
                    del self.pinned_users[target_id]
                    return f"تم تحرير تثبيت {target_username} 🔓"
                else:
                    return f"المستخدم {target_username} لم يكن مثبتاً."
            elif command == "-صعد":
                await self.highrise.teleport(target_user.id, Position(13.0, 12.5, 11.5))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
            elif command == "-ابعد":
                await self.highrise.teleport(target_user.id, Position(10.5, 0.0, 14.5))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
            elif command == "-حرف":
                await self.highrise.teleport(target_user.id, Position(x=14.5, y=3.5, z=0.5, facing='FrontRight'))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
            elif command == "-الوان":
                await self.highrise.teleport(target_user.id, Position(x=15.0, y=0.0, z=23.0, facing='BackLeft'))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
            elif command == "-ازياء":
                await self.highrise.teleport(target_user.id, Position(x=3.5, y=0.0, z=7.5, facing='FrontRight'))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
            elif command == "-vip":
                await self.highrise.teleport(target_user.id, Position(x=17.5, y=20.25, z=11.0, facing='FrontRight'))
                return f"تم إعادة {target_username} إلى الموقع الافتراضي."
        if is_admin:
            return admin_help_msg
        elif is_designer:
            return designer_help_msg
        else:
            return "⚠️ ليس لديك صلاحية لاستخدام هذه الأوامر."

    async def on_user_move(self, user: User, destination: Position | AnchorPosition) -> None:
        if user.id in self.pinned_users:
            create_task(self.background_task(self.handle_pinned_user_move, user))

    async def stop_loop(self, user_id: str):
        if user_id in self.active_loops:
            self.active_loops[user_id] = False
        if user_id in self.loop_tasks:
            self.loop_tasks[user_id].cancel()
            del self.loop_tasks[user_id]

    async def handle_pinned_user_move(self, user: User):
        saved_pos = self.pinned_users[user.id]["admin_location"]
        await self.highrise.teleport(user.id, saved_pos)

if __name__ == "__main__":
    arun(__main__.main([BotDefinition(Bot())]))
