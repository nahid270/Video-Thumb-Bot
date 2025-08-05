import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- আপনার বট এবং এপিআই কী ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- ওয়েব সার্ভার ও ওয়েবহুক এর জন্য ভ্যারিয়েবল ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
PORT = int(os.getenv("PORT", 8080))

# --- ভ্যারিয়েবল ঠিকমতো লোড হয়েছে কিনা তা পরীক্ষা করা ---
if not all([API_ID, API_HASH, BOT_TOKEN, WEBHOOK_URL]):
    raise ValueError("প্রয়োজনীয় ভ্যারিয়েবল (API_ID, API_HASH, BOT_TOKEN, WEBHOOK_URL) সেট করা নেই।")

API_ID = int(API_ID)

# --- আগের মতোই স্টোরেজ ---
video_pending = {}
user_cover = {}

app = Client("thumb_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)

def cleanup_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"ফাইল ডিলিট করতে সমস্যা: {path}: {e}")

BOT_COMMANDS = [
    types.BotCommand("start", "🤖 বট চালু করুন"),
    types.BotCommand("show_cover", "🖼️ সেভ করা কভার দেখুন"),
    types.BotCommand("del_cover", "🗑️ সেভ করা কভার মুছুন"),
]

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        "👋 হ্যালো!\n\n"
        "🤖 **Video Thumb Bot**-এ আপনাকে স্বাগতম।\n\n"
        "📌 **ব্যবহারের নিয়ম:**\n"
        "প্রথমে ছবি পাঠান, তারপর ভিডিও। অথবা প্রথমে ভিডিও, তারপর ছবি। বট স্বয়ংক্রিয়ভাবে থাম্বনেইল সেট করে দেবে।\n\n"
        "✅ **আপনার জন্য কমান্ডসমূহ:**\n"
        "➢ /show_cover - বর্তমানে সেভ করা কভার ছবিটি দেখতে।\n"
        "➢ /del_cover - সেভ করা কভার ছবিটি মুছে ফেলতে।\n\n"
        "এখনই একটি ছবি বা ভিডিও পাঠিয়ে কাজ শুরু করুন!"
    )

@app.on_message(filters.command("show_cover"))
async def show_cover(client: Client, message: Message):
    user_id = message.from_user.id
    cover_path = user_cover.get(user_id)
    if not cover_path or not os.path.exists(cover_path):
        await message.reply_text("❌ আপনার এখনো কোনো কভার সেভ করা নেই। প্রথমে একটি ছবি পাঠান।")
        return
    await client.send_photo(
        chat_id=message.chat.id,
        photo=cover_path,
        caption="📌 আপনার বর্তমানে সেভ করা কভার/থাম্বনেইল।"
    )

@app.on_message(filters.command("del_cover"))
async def del_cover(client: Client, message: Message):
    user_id = message.from_user.id
    cover_path = user_cover.pop(user_id, None)
    if cover_path:
        cleanup_file(cover_path)
        await message.reply_text("✅ আপনার সেভ করা কভার মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("❌ আপনার কাছে কোনো সেভ করা কভার ছিল না।")

# --- সংশোধিত লাইন ---
@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    # এডিট করা মেসেজ হলে কোনো সমস্যা নেই, তাই হ্যান্ডলারটি চলবে
    if message.from_user is None: return # চ্যানেল থেকে আসা মেসেজ উপেক্ষা করুন

    user_id = message.from_user.id
    old_cover_path = user_cover.get(user_id)
    cleanup_file(old_cover_path)
    
    status_msg = await message.reply_text("📥 কভার ছবিটি ডাউনলোড করা হচ্ছে...", quote=True)
    photo_path = await message.download(file_name=f"downloads/{user_id}_cover.jpg")
    user_cover[user_id] = photo_path

    pending_video = video_pending.get(user_id)
    if pending_video:
        await status_msg.edit_text("⏳ ভিডিও প্রসেস করা হচ্ছে...")
        try:
            await client.send_video(
                chat_id=pending_video["chat_id"],
                video=pending_video["video_path"],
                thumb=photo_path,
                caption="✅ আপনার ভিডিওর সাথে কাস্টম থাম্বনেইল যুক্ত করা হয়েছে।",
                reply_to_message_id=pending_video["video_msg_id"],
            )
            await status_msg.edit_text("🪄 ভিডিওটির জন্য কভার সেট করে পাঠিয়ে দেওয়া হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(pending_video.get("video_path"))
            video_pending.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ কভার ছবিটি সেভ করা হয়েছে। এখন একটি ভিডিও পাঠান।")

# --- সংশোধিত লাইন ---
@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    # এডিট করা মেসেজ হলে কোনো সমস্যা নেই, তাই হ্যান্ডলারটি চলবে
    if message.from_user is None: return # চ্যানেল থেকে আসা মেসেজ উপেক্ষা করুন

    user_id = message.from_user.id
    cover_path = user_cover.get(user_id)
    
    status_msg = await message.reply_text("📥 ভিডিওটি ডাউনলোড করা হচ্ছে...", quote=True)
    vid_path = await message.download(file_name=f"downloads/{user_id}_video.mp4")

    if cover_path and os.path.exists(cover_path):
        await status_msg.edit_text("⏳ ভিডিও প্রসেস করা হচ্ছে...")
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=vid_path,
                thumb=cover_path,
                caption="✅ আপনার ভিডিওটি সেভ করা কভারসহ পাঠানো হয়েছে।",
                reply_to_message_id=message.message_id,
            )
            await status_msg.edit_text("🎉 সফলভাবে কাস্টম কভারসহ ভিডিও পাঠানো হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(vid_path)
    else:
        old_pending_video = video_pending.get(user_id)
        if old_pending_video:
            cleanup_file(old_pending_video.get("video_path"))

        video_pending[user_id] = {
            "video_path": vid_path,
            "video_msg_id": message.message_id,
            "chat_id": message.chat.id,
        }
        await status_msg.edit_text("✔️ ভিডিও পেয়েছি। এখন একটি থাম্বনেইল (ছবি) পাঠান।")

# ওয়েবহুক হ্যান্ডলার এবং ওয়েব অ্যাপ্লিকেশন কোড অপরিবর্তিত
async def webhook_handler(request):
    try:
        update_data = await request.json()
        await app.feed_raw_update(update_data)
        return web.Response(status=200)
    except Exception as e:
        print(f"ওয়েবহুক হ্যান্ডলারে সমস্যা: {e}")
        return web.Response(status=500)

async def on_startup(web_app):
    print("ওয়েব অ্যাপ্লিকেশন চালু হচ্ছে...")
    if not os.path.isdir("downloads"):
        os.makedirs("downloads")
    
    await app.start()
    webhook_path = f"/{BOT_TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path

    try:
        await app.set_bot_webhook(url=full_webhook_url)
        await app.set_bot_commands(BOT_COMMANDS)
        print(f"ওয়েবহুক সেট করা হয়েছে: {full_webhook_url}")
        print("বট এখন চলছে...")
    except Exception as e:
        print(f"ওয়েবহুক সেট করতে ব্যর্থ: {e}")

async def on_shutdown(web_app):
    print("ওয়েব অ্যাপ্লিকেশন বন্ধ হচ্ছে...")
    await app.stop()
    print("বট বন্ধ হয়েছে।")

if __name__ == "__main__":
    web_app = web.Application()
    
    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)
    
    web_app.router.add_post(f"/{BOT_TOKEN}", webhook_handler)
    
    web.run_app(web_app, host="0.0.0.0", port=PORT)
