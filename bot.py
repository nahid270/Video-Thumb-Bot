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

# --- ভ্যারিয়েবল ঠিকমতো সেট করা আছে কিনা তা পরীক্ষা করা ---
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("প্রয়োজনীয় Environment Variables (API_ID, API_HASH, BOT_TOKEN) সেট করা নেই।")

API_ID = int(API_ID)

# --- অ্যাপ্লিকেশন স্টোরেজ (এখন আমরা file_id সেভ করব, ফাইলের পাথ নয়) ---
video_pending = {}  # {user_id: {"video_file_id": "...", "video_msg_id": ...}}
user_cover = {}     # {user_id: "photo_file_id"}

# --- Pyrogram ক্লায়েন্ট ---
app = Client("thumb_bot_fast", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- বট কমান্ড লিস্ট ---
BOT_COMMANDS = [
    types.BotCommand("start", "🤖 বট চালু করুন"),
    types.BotCommand("show_cover", "🖼️ সেভ করা কভার দেখুন"),
    types.BotCommand("del_cover", "🗑️ সেভ করা কভার মুছুন"),
]

# --- হ্যান্ডলার (এখন file_id ব্যবহার করে আপডেট করা) ---

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text("👋 হ্যালো! এই বটটি ফাইল ডাউনলোড না করেই দ্রুত থাম্বনেইল সেট করতে পারে।")

@app.on_message(filters.command("show_cover"))
async def show_cover(client: Client, message: Message):
    user_id = message.from_user.id
    cover_file_id = user_cover.get(user_id)
    if not cover_file_id:
        await message.reply_text("❌ আপনার এখনো কোনো কভার সেভ করা নেই।")
        return
    # সেভ করা file_id দিয়ে ছবি পাঠানো
    await client.send_photo(chat_id=message.chat.id, photo=cover_file_id, caption="📌 আপনার সেভ করা কভার/থাম্বনেইল।")

@app.on_message(filters.command("del_cover"))
async def del_cover(client: Client, message: Message):
    user_id = message.from_user.id
    if user_cover.pop(user_id, None):
        await message.reply_text("✅ আপনার সেভ করা কভার মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("❌ আপনার কাছে কোনো সেভ করা কভার ছিল না।")

@app.on_message(filters.photo)
async def receive_photo(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    
    # ছবির file_id সেভ করা
    photo_file_id = message.photo.file_id
    user_cover[user_id] = photo_file_id

    pending_video = video_pending.get(user_id)
    if pending_video:
        status_msg = await message.reply_text("⏳ প্রসেস করা হচ্ছে...", quote=True)
        try:
            # ডাউনলোড/আপলোড ছাড়া সরাসরি file_id দিয়ে ভিডিও পাঠানো
            await client.send_video(
                chat_id=message.chat.id,
                video=pending_video["video_file_id"],
                thumb=photo_file_id,
                caption="✅ আপনার ভিডিওর সাথে কাস্টম থাম্বনেইল যুক্ত করা হয়েছে।",
                reply_to_message_id=pending_video["video_msg_id"]
            )
            await status_msg.delete() # স্ট্যাটাস মেসেজ ডিলিট করে দেওয়া
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
        finally:
            video_pending.pop(user_id, None)
    else:
        await message.reply_text("✔️ কভার ছবিটি সেভ করা হয়েছে। এখন একটি ভিডিও পাঠান।", quote=True)

@app.on_message(filters.video)
async def receive_video(client: Client, message: Message):
    if message.from_user is None: return
    user_id = message.from_user.id
    
    video_file_id = message.video.file_id
    cover_file_id = user_cover.get(user_id)
    
    status_msg = await message.reply_text("⏳ প্রসেস করা হচ্ছে...", quote=True)

    if cover_file_id:
        try:
            # ডাউনলোড/আপলোড ছাড়া সরাসরি file_id দিয়ে ভিডিও পাঠানো
            await client.send_video(
                chat_id=message.chat.id,
                video=video_file_id,
                thumb=cover_file_id,
                caption="✅ আপনার ভিডিওটি সেভ করা কভারসহ পাঠানো হয়েছে।",
                reply_to_message_id=message.message_id
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ পাঠাতে সমস্যা হয়েছে: {e}")
    else:
        # কোনো কভার সেভ করা না থাকলে, ভিডিওর file_id সেভ করে রাখা
        video_pending[user_id] = {
            "video_file_id": video_file_id,
            "video_msg_id": message.message_id
        }
        await status_msg.edit_text("✔️ ভিডিও পেয়েছি। এখন একটি থাম্বনেইল (ছবি) পাঠান।")

# --- ওয়েব সার্ভার এবং মূল ফাংশন (আগের মতোই) ---
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
    await app.set_bot_commands(BOT_COMMANDS)
    print("🚀 বট এখন অনলাইনে আছে এবং পোলিং মোডে মেসেজের জন্য অপেক্ষা করছে...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        app.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("বট বন্ধ করা হলো।")
