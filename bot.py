import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web

# --- .env ফাইল থেকে ভ্যারিয়েবল লোড করা ---
load_dotenv()

# --- প্রয়োজনীয় ভ্যারিয়েবল লোড করা ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
# --- ★★★ নতুন ভ্যারিয়েবল: লগ চ্যানেল আইডি ★★★ ---
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

# --- ভ্যারিয়েবল ঠিকমতো সেট করা আছে কিনা তা পরীক্ষা করা ---
if not all([API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID]):
    raise ValueError("প্রয়োজনীয় Environment Variables (API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL_ID) সেট করা নেই।")

API_ID = int(API_ID)

# --- অ্যাপ্লিকেশন স্টোরেজ ---
user_data = {} # {user_id: {"cover_id": "...", "video_id": "...", "video_msg_id": ...}}

app = Client("thumb_bot_final", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ★★★ নতুন ফাংশন: ফাইল ফরোয়ার্ড করে নতুন file_id পাওয়া ★★★ ---
async def get_new_file_id(file_id):
    try:
        # ফাইলটি লগ চ্যানেলে ফরোয়ার্ড করা
        forwarded_message = await app.send_cached_media(
            chat_id=LOG_CHANNEL_ID,
            file_id=file_id
        )
        # ফরোয়ার্ড করা মেসেজ থেকে নতুন file_id সংগ্রহ করা
        if forwarded_message.video:
            return forwarded_message.video.file_id
        elif forwarded_message.photo:
            return forwarded_message.photo.file_id
        return None
    except Exception as e:
        print(f"লগ চ্যানেলে ফরোয়ার্ড করতে সমস্যা: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user_data.pop(message.from_user.id, None) # শুরু করলে ডেটা রিসেট
    await message.reply_text("👋 হ্যালো! ছবি ও ভিডিও পাঠান, আমি থাম্বনেইল সেট করে দেব।")

# --- ডিলিট এবং শো কমান্ড এখন প্রয়োজন নেই, কারণ ফ্লো সহজ করা হয়েছে ---
# আপনি চাইলে এগুলো রাখতে পারেন, তবে মূল কার্যকারিতার জন্য এখন আর জরুরি নয়।

@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    
    status_msg = await message.reply_text("🖼️ ছবি পেয়েছি, প্রসেস করছি...", quote=True)
    
    new_photo_id = await get_new_file_id(message.photo.file_id)
    if not new_photo_id:
        await status_msg.edit_text("❌ ছবি প্রসেস করতে সমস্যা হয়েছে।")
        return

    # ইউজারের ডেটা ইনিশিয়ালাইজ করা
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['cover_id'] = new_photo_id
    
    # যদি আগে ভিডিও এসে থাকে, তাহলে এখন একসাথে পাঠাও
    if 'video_id' in user_data[user_id]:
        await status_msg.edit_text("⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=user_data[user_id]['video_id'],
                thumb=user_data[user_id]['cover_id'],
                caption="✅ সফলভাবে থাম্বনেইল সেট করা হয়েছে।",
                reply_to_message_id=user_data[user_id]['video_msg_id']
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            user_data.pop(user_id, None) # কাজ শেষে ডেটা মুছে ফেলা
    else:
        await status_msg.edit_text("✔️ কভার ছবি প্রস্তুত। এখন ভিডিও পাঠান।")

@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id

    status_msg = await message.reply_text("🎬 ভিডিও পেয়েছি, প্রসেস করছি...", quote=True)

    new_video_id = await get_new_file_id(message.video.file_id)
    if not new_video_id:
        await status_msg.edit_text("❌ ভিডিও প্রসেস করতে সমস্যা হয়েছে।")
        return
        
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]['video_id'] = new_video_id
    user_data[user_id]['video_msg_id'] = message.id
    
    if 'cover_id' in user_data[user_id]:
        await status_msg.edit_text("⏳ ভিডিও এবং থাম্বনেইল একত্রিত করছি...")
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=user_data[user_id]['video_id'],
                thumb=user_data[user_id]['cover_id'],
                caption="✅ সফলভাবে থাম্বনেইল সেট করা হয়েছে।",
                reply_to_message_id=message.id
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            user_data.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ ভিডিও প্রস্তুত। এখন থাম্বনেইলের জন্য ছবি পাঠান।")


# --- ওয়েব সার্ভার এবং মূল ফাংশন (অপরিবর্তিত) ---
async def ping_handler(request):
    return web.Response(text="I am alive!", status=200)

async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get("/", ping_handler)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ ওয়েব সার্ভার পিং গ্রহণের জন্য প্রস্তুত http://0.0.0.0:{PORT} পোর্টে")

async def main():
    await asyncio.gather(app.start(), start_web_server())
    # কমান্ড সেট করার প্রয়োজন নেই কারণ আমরা সেগুলো বাদ দিয়েছি
    # await app.set_bot_commands(BOT_COMMANDS) 
    print("🚀 বট এখন অনলাইনে আছে এবং পোলিং মোডে মেসেজের জন্য অপেক্ষা করছে...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        app.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("বট বন্ধ করা হলো।")
