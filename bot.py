import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web

# --- ধাপ ১: .env ফাইল থেকে ভ্যারিয়েবল লোড করা ---
load_dotenv()

# --- আপনার বট এবং এপিআই কী ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
PORT = int(os.getenv("PORT", 8080))

# --- স্বয়ংক্রিয়ভাবে সমস্যা পরীক্ষা করা ---
# এই কোডটি নিশ্চিত করবে যে Render-এ সব ভ্যারিয়েবল ঠিকমতো দেওয়া আছে
if not all([API_ID, API_HASH, BOT_TOKEN, WEBHOOK_URL]):
    error_message = """
    !!! মারাত্মক সমস্যা !!!
    প্রয়োজনীয় সব Environment Variables সেট করা নেই।
    অনুগ্রহ করে Render ড্যাশবোর্ডের 'Environment' সেকশনে যান এবং নিচের সবগুলো ভ্যারিয়েবল সেট করুন:
    - API_ID
    - API_HASH
    - BOT_TOKEN
    - WEBHOOK_URL (আপনার Render অ্যাপের লিংক, যেমন: https://your-app-name.onrender.com)
    """
    raise ValueError(error_message)

try:
    API_ID = int(API_ID)
except ValueError:
    raise ValueError("API_ID অবশ্যই একটি সংখ্যা হতে হবে।")


# --- অ্যাপ্লিকেশন স্টোরেজ ---
video_pending = {}
user_cover = {}

# --- Pyrogram ক্লায়েন্ট (ওয়েবহুকের জন্য প্রস্তুত) ---
app = Client("thumb_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)

# --- ফাইল পরিষ্কার করার ফাংশন ---
def cleanup_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"ফাইল ডিলিট করতে সমস্যা: {path}: {e}")

# --- বট কমান্ড লিস্ট ---
BOT_COMMANDS = [
    types.BotCommand("start", "🤖 বট চালু করুন"),
    types.BotCommand("show_cover", "🖼️ সেভ করা কভার দেখুন"),
    types.BotCommand("del_cover", "🗑️ সেভ করা কভার মুছুন"),
]

# --- কমান্ড এবং মেসেজ হ্যান্ডলার (আপনার আগের কোডের মতোই) ---

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
    await client.send_photo(chat_id=message.chat.id, photo=cover_path, caption="📌 আপনার বর্তমানে সেভ করা কভার/থাম্বনেইল।")

@app.on_message(filters.command("del_cover"))
async def del_cover(client: Client, message: Message):
    user_id = message.from_user.id
    cover_path = user_cover.pop(user_id, None)
    if cover_path:
        cleanup_file(cover_path)
        await message.reply_text("✅ আপনার সেভ করা কভার মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("❌ আপনার কাছে কোনো সেভ করা কভার ছিল না।")

@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    cleanup_file(user_cover.get(user_id))
    status_msg = await message.reply_text("📥 কভার ছবিটি ডাউনলোড করা হচ্ছে...", quote=True)
    photo_path = await message.download(file_name=f"downloads/{user_id}_cover.jpg")
    user_cover[user_id] = photo_path
    pending_video = video_pending.get(user_id)
    if pending_video:
        await status_msg.edit_text("⏳ ভিডিও প্রসেস করা হচ্ছে...")
        try:
            await client.send_video(chat_id=pending_video["chat_id"], video=pending_video["video_path"], thumb=photo_path, caption="✅ আপনার ভিডিওর সাথে কাস্টম থাম্বনেইল যুক্ত করা হয়েছে।", reply_to_message_id=pending_video["video_msg_id"])
            await status_msg.edit_text("🪄 ভিডিওটির জন্য কভার সেট করে পাঠিয়ে দেওয়া হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(pending_video.get("video_path"))
            video_pending.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ কভার ছবিটি সেভ করা হয়েছে। এখন একটি ভিডিও পাঠান।")

@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    cover_path = user_cover.get(user_id)
    status_msg = await message.reply_text("📥 ভিডিওটি ডাউনলোড করা হচ্ছে...", quote=True)
    vid_path = await message.download(file_name=f"downloads/{user_id}_video.mp4")
    if cover_path and os.path.exists(cover_path):
        await status_msg.edit_text("⏳ ভিডিও প্রসেস করা হচ্ছে...")
        try:
            await client.send_video(chat_id=message.chat.id, video=vid_path, thumb=cover_path, caption="✅ আপনার ভিডিওটি সেভ করা কভারসহ পাঠানো হয়েছে।", reply_to_message_id=message.message_id)
            await status_msg.edit_text("🎉 সফলভাবে কাস্টম কভারসহ ভিডিও পাঠানো হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ ভিডিও পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(vid_path)
    else:
        cleanup_file(video_pending.get(user_id, {}).get("video_path"))
        video_pending[user_id] = {"video_path": vid_path, "video_msg_id": message.message_id, "chat_id": message.chat.id}
        await status_msg.edit_text("✔️ ভিডিও পেয়েছি। এখন একটি থাম্বনেইল (ছবি) পাঠান।")

# --- ওয়েবহুক হ্যান্ডলার এবং ওয়েব অ্যাপ্লিকেশন ---

async def webhook_handler(request):
    try:
        update_data = await request.json()
        await app.feed_raw_update(update_data)
        return web.Response(status=200)
    except Exception as e:
        print(f"ওয়েবহুক হ্যান্ডলারে সমস্যা: {e}")
        return web.Response(status=500)

async def on_startup(web_app):
    print("--- বট চালু করার প্রক্রিয়া শুরু হচ্ছে ---")
    if not os.path.isdir("downloads"):
        os.makedirs("downloads")
    
    await app.start()
    
    # ওয়েবহুক URL তৈরি এবং টেলিগ্রামের কাছে সেট করা
    webhook_path = f"/{BOT_TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    try:
        print(f"টেলিগ্রামের কাছে ওয়েবহুক সেট করার চেষ্টা চলছে: {full_webhook_url}")
        await app.set_bot_webhook(url=full_webhook_url)
        await app.set_bot_commands(BOT_COMMANDS)
        print("✅ সফলভাবে ওয়েবহুক এবং কমান্ড সেট করা হয়েছে।")
        print("🚀 বট এখন অনলাইনে আছে এবং মেসেজ গ্রহণের জন্য প্রস্তুত।")
    except Exception as e:
        print(f"!!! ওয়েবহুক সেট করতে মারাত্মক সমস্যা: {e}")
        print("সমাধান: আপনার BOT_TOKEN এবং WEBHOOK_URL সঠিক কিনা তা পরীক্ষা করুন।")

async def on_shutdown(web_app):
    print("--- বট বন্ধ হচ্ছে ---")
    await app.stop()

if __name__ == "__main__":
    web_app = web.Application()
    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)
    web_app.router.add_post(f"/{BOT_TOKEN}", webhook_handler)
    
    print(f"ওয়েব সার্ভার চালু হচ্ছে http://0.0.0.0:{PORT} পোর্টে")
    web.run_app(web_app, host="0.0.0.0", port=PORT)
