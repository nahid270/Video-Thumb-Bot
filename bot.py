import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web
from PIL import Image

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

def create_thumbnail(file_path: str) -> str:
    try:
        thumb_path = f"{file_path}_thumb.jpg"
        with Image.open(file_path) as img:
            img.thumbnail((320, 320))
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

# --- ★★★ নতুন হেল্পার ফাংশন: মেসেজ এডিট করার জন্য ★★★ ---
async def edit_status(message: Message, new_text: str):
    """
    মেসেজ এডিট করে, কিন্তু যদি টেক্সট একই থাকে তাহলে এরর এড়ানোর জন্য কিছু করে না।
    """
    try:
        # যদি বর্তমান টেক্সট এবং নতুন টেক্সট ভিন্ন হয়, তবেই এডিট করবে
        if message.text != new_text:
            await message.edit_text(new_text)
    except Exception as e:
        # MessageNotModified এরর উপেক্ষা করা
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            print(f"মেসেজ এডিট করতে সমস্যা: {e}")

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    cleanup_files(user_data.get(user_id, {}).get("thumb_path"))
    user_data.pop(user_id, None)
    await message.reply_text("👋 হ্যালো! ছবি ও ভিডিও পাঠান, আমি থাম্বনেইল সেট করে দেব।")

@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    
    status_msg = await message.reply_text("🖼️ ছবি ডাউনলোড ও প্রসেস করছি...", quote=True)
    
    original_photo_path = await message.download(file_name=f"downloads/{message.id}_original.jpg")
    thumb_path = create_thumbnail(original_photo_path)
    
    if not thumb_path:
        await edit_status(status_msg, "❌ এই ছবিটি প্রসেস করা যাচ্ছে না। অন্য একটি ছবি চেষ্টা করুন।")
        cleanup_files(original_photo_path)
        return

    if user_id not in user_data:
        user_data[user_id] = {}
    
    cleanup_files(user_data[user_id].get("thumb_path"))
    user_data[user_id]['thumb_path'] = thumb_path
    user_data[user_id]['status_msg_id'] = status_msg.id # ★★★ স্ট্যাটাস মেসেজের আইডি সেভ করা
    
    if 'video_id' in user_data[user_id]:
        await edit_status(status_msg, "⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
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
            await edit_status(status_msg, f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_files(user_data[user_id].get("thumb_path"))
            user_data.pop(user_id, None)
    else:
        # ★★★ নতুন হেল্পার ফাংশন ব্যবহার করা হচ্ছে ★★★
        await edit_status(status_msg, "✔️ কভার ছবি প্রস্তুত। এখন ভিডিও পাঠান।")
    
    cleanup_files(original_photo_path)

@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id

    status_msg = await message.reply_text("🎬 ভিডিও প্রসেস করছি...", quote=True)

    new_video_id = await get_new_file_id(message)
    if not new_video_id:
        await edit_status(status_msg, "❌ ভিডিও প্রসেস করতে সমস্যা হয়েছে।")
        return
        
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]['video_id'] = new_video_id
    user_data[user_id]['video_msg_id'] = message.id
    
    if 'thumb_path' in user_data[user_id]:
        # আগের স্ট্যাটাস মেসেজটি পাওয়া এবং এডিট করা
        try:
            status_msg_id = user_data[user_id].get('status_msg_id')
            if status_msg_id:
                await client.delete_messages(chat_id=message.chat.id, message_ids=status_msg.id)
                status_msg_to_edit = await client.get_messages(chat_id=message.chat.id, message_ids=status_msg_id)
                await edit_status(status_msg_to_edit, "⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
            else: # যদি কোনো কারণে স্ট্যাটাস মেসেজ না পাওয়া যায়
                status_msg_to_edit = status_msg
        except:
             status_msg_to_edit = status_msg

        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=user_data[user_id]['video_id'],
                thumb=user_data[user_id]['thumb_path'],
                caption="✅ সফলভাবে থাম্বনেইল সেট করা হয়েছে।",
                reply_to_message_id=message.id
            )
            await status_msg_to_edit.delete()
        except Exception as e:
            await edit_status(status_msg_to_edit, f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_files(user_data[user_id].get("thumb_path"))
            user_data.pop(user_id, None)
    else:
        await edit_status(status_msg, "✔️ ভিডিও প্রস্তুত। এখন থাম্বনেইলের জন্য ছবি পাঠান।")

# --- ওয়েব সার্ভার এবং মূল ফাংশন (অপরিবর্তিত) ---

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
