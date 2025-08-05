import os
import asyncio
from pyrogram import Client, filters, types
from pyrogram.types import Message
from dotenv import load_dotenv
from aiohttp import web

# --- ধাপ ১: .env ফাইল থেকে ভ্যারিয়েবল লোড করা ---
load_dotenv()

# --- প্রয়োজনীয় ভ্যারিয়েবল লোড করা ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080)) # Render এই পোর্টটি ব্যবহার করবে

# --- ভ্যারিয়েবল ঠিকমতো সেট করা আছে কিনা তা পরীক্ষা করা ---
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("প্রয়োজনীয় Environment Variables (API_ID, API_HASH, BOT_TOKEN) সেট করা নেই।")

API_ID = int(API_ID)

# --- অ্যাপ্লিকেশন স্টোরেজ ---
video_pending = {}
user_cover = {}

# --- Pyrogram ক্লায়েন্ট (পোলিং মোডের জন্য) ---
app = Client("thumb_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

# --- হ্যান্ডলারগুলো অপরিবর্তিত ---
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text("👋 হ্যালো! বটটি সফলভাবে চলছে।")

@app.on_message(filters.command("show_cover"))
async def show_cover(client: Client, message: Message):
    user_id = message.from_user.id
    cover_path = user_cover.get(user_id)
    if not cover_path or not os.path.exists(cover_path):
        await message.reply_text("❌ আপনার এখনো কোনো কভার সেভ করা নেই।")
        return
    await client.send_photo(chat_id=message.chat.id, photo=cover_path, caption="📌 আপনার সেভ করা কভার/থাম্বনেইল।")

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
            await client.send_video(chat_id=pending_video["chat_id"], video=pending_video["video_path"], thumb=photo_path, caption="✅ কাস্টম থাম্বনেইলসহ ভিডিও পাঠানো হয়েছে।", reply_to_message_id=pending_video["video_msg_id"])
            await status_msg.edit_text("🪄 ভিডিওর জন্য কভার সেট করা হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(pending_video.get("video_path"))
            video_pending.pop(user_id, None)
    else:
        await status_msg.edit_text("✔️ কভার ছবি সেভ করা হয়েছে। এখন ভিডিও পাঠান।")

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
            await client.send_video(chat_id=message.chat.id, video=vid_path, thumb=cover_path, caption="✅ সেভ করা কভারসহ ভিডিও পাঠানো হয়েছে।", reply_to_message_id=message.message_id)
            await status_msg.edit_text("🎉 সফলভাবে পাঠানো হয়েছে।")
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            cleanup_file(vid_path)
    else:
        cleanup_file(video_pending.get(user_id, {}).get("video_path"))
        video_pending[user_id] = {"video_path": vid_path, "video_msg_id": message.message_id, "chat_id": message.chat.id}
        await status_msg.edit_text("✔️ ভিডিও পেয়েছি। এখন থাম্বনেইল ছবি পাঠান।")


# --- ওয়েব সার্ভার যা Render-কে সচল রাখবে ---
async def ping_handler(request):
    """এই হ্যান্ডলারটি শুধু একটি সফল রেসপন্স পাঠাবে, যাতে Render অ্যাপটিকে সচল রাখে।"""
    return web.Response(text="I am alive!", status=200)

async def start_web_server():
    """একটি ছোট ওয়েব সার্ভার চালু করে।"""
    web_app = web.Application()
    web_app.router.add_get("/", ping_handler) # রুট URL-এ পিং হ্যান্ডলার যোগ করা
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ ওয়েব সার্ভার পিং গ্রহণের জন্য প্রস্তুত http://0.0.0.0:{PORT} পোর্টে")

# --- মূল ফাংশন যা বট এবং ওয়েব সার্ভার উভয়ই চালু করবে ---
async def main():
    print("--- বট চালু করার প্রক্রিয়া শুরু হচ্ছে ---")
    if not os.path.isdir("downloads"):
        os.makedirs("downloads")
    
    # বট এবং ওয়েব সার্ভার একসাথে (concurrently) চালানো
    await asyncio.gather(
        app.start(),
        start_web_server()
    )
    
    await app.set_bot_commands(BOT_COMMANDS)
    print("🚀 বট এখন অনলাইনে আছে এবং পোলিং মোডে মেসেজের জন্য অপেক্ষা করছে...")
    
    # বটকে অনির্দিষ্টকালের জন্য চলতে দেওয়া
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        app.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("বট বন্ধ করা হলো।")
