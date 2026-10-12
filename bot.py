import os
import time
import math
import subprocess
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
from deep_translator import GoogleTranslator
import edge_tts

# .env থেকে কনফিগারেশন লোড করা
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = Client("dubbing_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

VOICES = {
    "bn": "bn-BD-NabanitaNeural",  # বাংলা
    "hi": "hi-IN-MadhurNeural",    # হিন্দি
    "en": "en-US-GuyNeural"        # ইংরেজি
}

user_data = {}
last_update_time = {}

# 📊 লাইভ প্রগ্রেস বার বানানোর ফাংশন
async def progress_bar(current, total, message, action_name):
    now = time.time()
    msg_id = message.id

    # টেলিগ্রাম ব্লক এড়াতে প্রতি ৩.৫ সেকেন্ড পর পর বা ১০০% হলে আপডেট হবে
    if current != total and (now - last_update_time.get(msg_id, 0)) < 3.5:
        return

    last_update_time[msg_id] = now

    percentage = (current / total) * 100
    bar_length = 10
    filled = int((current / total) * bar_length)
    bar = "▰" * filled + "▱" * (bar_length - filled)

    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)

    text = (
        f"⏳ **{action_name}...**\n\n"
        f"[{bar}] {percentage:.1f}%\n"
        f"📊 সাইজ: {current_mb:.1f} MB / {total_mb:.1f} MB"
    )

    try:
        await message.edit_text(text)
    except Exception:
        pass

# বড় টেক্সট অনুবাদ ফাংশন
def translate_large_text(text, target_lang):
    chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
    translated_parts = []
    translator = GoogleTranslator(source='auto', target=target_lang)
    for chunk in chunks:
        translated_parts.append(translator.translate(chunk))
    return " ".join(translated_parts)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! আমাকে যেকোনো ভাষার ভিডিও পাঠান, আমি লাইভ প্রগ্রেস বার সহ ডাবিং করে দেব।")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    file = message.video or message.document
    if not file.file_name and not message.video:
        return

    if file.file_size > 1900 * 1024 * 1024:
        await message.reply_text("⚠️ ফাইলটি অনেক বড়! ২ জিবির নিচের ভিডিও পাঠান।")
        return

    msg = await message.reply_text("⏳ ডাউনলোডের প্রস্তুতি নেওয়া হচ্ছে...")
    user_id = str(message.from_user.id)
    input_video = f"{user_id}_input.mp4"

    # লাইভ ডাউনলোড প্রগ্রেস বার সহ ডাউনলোড
    await client.download_media(
        message, 
        file_name=input_video,
        progress=progress_bar,
        progress_args=(msg, "ভিডিও ডাউনলোড হচ্ছে")
    )
    user_data[user_id] = input_video

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="bn"),
         InlineKeyboardButton("🇮🇳 হিন্দি", callback_data="hi"),
         InlineKeyboardButton("🇺🇸 ইংরেজি", callback_data="en")]
    ])
    await msg.edit_text("✅ ডাউনলোড সম্পূর্ণ!\nএখন কোন ভাষায় ডাব করতে চান সিলেক্ট করুন:", reply_markup=markup)

@app.on_callback_query()
async def process_dubbing(client, callback_query):
    user_id = str(callback_query.from_user.id)
    target_lang = callback_query.data

    if user_id not in user_data:
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি! আবার পাঠান।")
        return

    input_video = user_data[user_id]
    extracted_audio = f"{user_id}_audio.mp3"
    tts_audio = f"{user_id}_tts.mp3"
    final_video = f"{user_id}_dubbed.mp4"

    status_msg = await callback_query.message.edit_text("⚙️ ডাবিং শুরু হচ্ছে...")

    try:
        # ১. অডিও আলাদা
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▱▱▱] ২৫%\n🔹 অডিও আলাদা ও কমপ্রেস করা হচ্ছে...")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ২. Groq Cloud (Whisper)
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▱▱] ৫০%\n🔹 কথা থেকে টেক্সটে রূপান্তর হচ্ছে (Groq AI)...")
        with open(extracted_audio, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(extracted_audio, file.read()),
                model="whisper-large-v3",
                response_format="text"
            )

        original_text = str(transcription).strip()
        if not original_text:
            raise Exception("ভিডিওতে কোনো কথা শনাক্ত করা যায়নি!")

        # ৩. অনুবাদ ও ভয়েস তৈরি
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▱] ৭৫%\n🔹 অনুবাদ ও নতুন AI কণ্ঠ তৈরি হচ্ছে...")
        translated_text = translate_large_text(original_text, target_lang)

        voice = VOICES.get(target_lang, "bn-BD-NabanitaNeural")
        communicate = edge_tts.Communicate(translated_text, voice)
        await communicate.save(tts_audio)

        # ৪. ভিডিও রেন্ডারিং
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▰] ৯০%\n🔹 ভিডিওতে নতুন ডাবিং সাউন্ড যুক্ত করা হচ্ছে...")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video, "-i", tts_audio,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", final_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৫. লাইভ আপলোড প্রগ্রেস বার সহ টেলিগ্রামে পাঠানো
        await status_msg.edit_text("🚀 ভিডিও তৈরি শেষ! আপলোড শুরু হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption="🎉 ডাবিং সম্পন্ন হয়েছে!",
            supports_streaming=True,
            progress=progress_bar,
            progress_args=(status_msg, "ভিডিও আপলোড হচ্ছে")
        )

    except Exception as e:
        await callback_query.message.reply_text(f"❌ এরর: {str(e)}")

    finally:
        for path in [input_video, extracted_audio, tts_audio, final_video]:
            if os.path.exists(path):
                os.remove(path)
        if user_id in user_data:
            del user_data[user_id]
        try:
            await status_msg.delete()
        except Exception:
            pass

print("Live Progress Bar সহ বট চালু হয়েছে...")
app.run()
