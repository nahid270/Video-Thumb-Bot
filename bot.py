import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web
from PIL import Image # ★★★ Pillow লাইব্রেরি ইম্পোর্ট করা হলো ★★★

# --- .env ফাইল থেকে ভ্যারিয়েবল লোড করা ---
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
LOG_CHANNEL_ID_STR = os.getenv("LOG_CHANNEL_ID")

if not all([API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID_STR]):
    raise ValueError("প্রয়োজনীয় Environment Variables সেট করা নেই।")

API_ID = int(API_ID)
LOG_CHANNEL_ID = int(LOG_CHANNEL_ID_STR)

# --- অ্যাপ্লিকেশন স্টোরেজ ---
user_data = {}

app = Client("thumb_bot_final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ফাইল পরিষ্কার করার ফাংশন ---
def cleanup_files(*paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"ফাইল ডিলিট করতে সমস্যা: {path}: {e}")

# --- ★★★ নতুন ফাংশন: সঠিক থাম্বনেইল তৈরি করা ★★★ ---
def create_thumbnail(file_path: str) -> str:
    try:
        thumb_path = f"{file_path}_thumb.jpg"
        with Image.open(file_path) as img:
            # থাম্বনেইল সাইজ 320x320 এর মধ্যে রাখা হচ্ছে
            img.thumbnail((320, 320))
            # RGBA (PNG) হলে RGB (JPEG) তে কনভার্ট করা
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(thumb_path, "JPEG")
        return thumb_path
    except Exception as e:
        print(f"থাম্বনেইল তৈরি করতে সমস্যা: {e}")
        return None

async def get_new_file_id(message: Message):
    try:
        copied_message = await message.copy(chat_id=LOG_CHANNEL_ID)
        return copied_message.video.file_id if copied_message.video else None
    except Exception as e:
        print(f"লগ চ্যানেলে মেসেজ কপি করতে সমস্যা: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user_data.pop(message.from_user.id, None)
    await message.reply_text("👋 হ্যালো! ছবি ও ভিডিও পাঠান, আমি থাম্বনেইল সেট করে দেব।")

@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    
    status_msg = await message.reply_text("🖼️ ছবি ডাউনলোড ও প্রসেস করছি...", quote=True)
    
    # ছবিটি ডাউনলোড করা হচ্ছে
    original_photo_path = await message.download(file_name=f"downloads/{message.id}_original.jpg")
    
    # ডাউনলোড করা ছবি থেকে সঠিক থাম্বনেইল তৈরি করা
    thumb_path = create_thumbnail(original_photo_path)
    
    if not thumb_path:
        await status_msg.edit_text("❌ এই ছবিটি প্রসেস করা যাচ্ছে না। অন্য একটি ছবি চেষ্টা করুন।")
        cleanup_files(original_photo_path)
        return

    if user_id not in user_data:
        user_data[user_id] = {}
    
    # আগের থাম্বনেইল থাকলে সেটি ডিলিট করা
    cleanup_files(user_data[user_id].get("thumb_path"))
    user_data[user_id]['thumb_path'] = thumb_path
    
    if 'video_id' in user_data[user_id]:
        await status_msg.edit_text("⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=user_data[user_id]['video_id'],
                thumb=user_data[user_id]['thumb_path'],
                caption="✅ সফলভাবে থাম্বনেইল সেট করা হয়েছে।",
                reply_to_message_id=user_data[user_id]['video_msg_id']
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_files(user_data[user_id].get("thumb_path"))
            user_data.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ কভার ছবি প্রস্তুত। এখন ভিডিও পাঠান।")
    
    # আসল ডাউনলোড করা ছবিটি ডিলিট করে দেওয়া
    cleanup_files(original_photo_path)

@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id

    status_msg = await message.reply_text("🎬 ভিডিও প্রসেস করছি...", quote=True)

    new_video_id = await get_new_file_id(message)
    if not new_video_id:
        await status_msg.edit_text("❌ ভিডিও প্রসেস করতে সমস্যা হয়েছে।")
        return
        
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]['video_id'] = new_video_id
    user_data[user_id]['video_msg_id'] = message.id
    
    if 'thumb_path' in user_data[user_id]:
        await status_msg.edit_text("⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=user_data[user_id]['video_id'],
                thumb=user_data[user_id]['thumb_path'],
                caption="✅ সফলভাবে থাম্বনেইল সেট করা হয়েছে।",
                reply_to_message_id=message.id
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_files(user_data[user_id].get("thumb_path"))
            user_data.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ ভিডিও প্রস্তুত। এখন থাম্বনেইলের জন্য ছবি পাঠান।")

async def on_startup(web_app):
    if not os.path.isdir("downloads"):
        os.makedirs("downloads")
    await asyncio.gather(app.start(), start_web_server())
    print("🚀 বট এখন অনলাইনে আছে।")

async def start_web_server():
    web_app = web.Application()
    async def ping_handler(request):
        return web.Response(text="alive", status=200)
    web_app.router.add_get("/", ping_handler)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup(None))
    loop.run_forever()
