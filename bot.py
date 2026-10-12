import os
import subprocess
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
from deep_translator import GoogleTranslator
import edge_tts

# .env ফাইল থেকে কনফিগারেশন লোড করা
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

def translate_large_text(text, target_lang):
    chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
    translated_parts = []
    translator = GoogleTranslator(source='auto', target=target_lang)
    for chunk in chunks:
        translated_parts.append(translator.translate(chunk))
    return " ".join(translated_parts)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! আমাকে যেকোনো ভাষার ভিডিও পাঠান (সর্বোচ্চ ১.৫ জিবি), আমি ডাবিং করে দেব।")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    file = message.video or message.document
    if not file.file_name and not message.video:
        return

    if file.file_size > 1900 * 1024 * 1024:
        await message.reply_text("⚠️ ফাইলটি অনেক বড়! ২ জিবির নিচের ভিডিও পাঠান।")
        return

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে...")
    user_id = str(message.from_user.id)
    input_video = f"{user_id}_input.mp4"

    await client.download_media(message, file_name=input_video)
    user_data[user_id] = input_video

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="bn"),
         InlineKeyboardButton("🇮🇳 হিন্দি", callback_data="hi"),
         InlineKeyboardButton("🇺🇸 ইংরেজি", callback_data="en")]
    ])
    await msg.edit_text("ভিডিও ডাউনলোড হয়েছে! কোন ভাষায় ডাব করতে চান?", reply_markup=markup)

@app.on_callback_query()
async def process_dubbing(client, callback_query):
    user_id = str(callback_query.from_user.id)
    target_lang = callback_query.data

    if user_id not in user_data:
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি!")
        return

    input_video = user_data[user_id]
    extracted_audio = f"{user_id}_audio.mp3"
    tts_audio = f"{user_id}_tts.mp3"
    final_video = f"{user_id}_dubbed.mp4"

    status_msg = await callback_query.message.edit_text("⚙️ প্রসেসিং শুরু হয়েছে...\n১/৪ অডিও আলাদা করা হচ্ছে...")

    try:
        # ১. FFmpeg: অডিও কম্প্রেশন
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ২. Groq Cloud (Whisper)
        await status_msg.edit_text("⚙️ ২/৪ ভয়েস থেকে টেক্সটে রূপান্তর হচ্ছে...")
        with open(extracted_audio, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(extracted_audio, file.read()),
                model="whisper-large-v3",
                response_format="text"
            )

        original_text = str(transcription).strip()
        if not original_text:
            raise Exception("ভিডিওতে কোনো কথা শনাক্ত করা যায়নি!")

        # ৩. অনুবাদ
        await status_msg.edit_text("⚙️ ৩/৪ অনুবাদ করা হচ্ছে...")
        translated_text = translate_large_text(original_text, target_lang)

        # ৪. Edge-TTS ভয়েস
        await status_msg.edit_text("⚙️ ৪/৪ AI ভয়েস তৈরি করা হচ্ছে...")
        voice = VOICES.get(target_lang, "bn-BD-NabanitaNeural")
        communicate = edge_tts.Communicate(translated_text, voice)
        await communicate.save(tts_audio)

        # ৫. ভিডিও রেন্ডারিং
        await status_msg.edit_text("⚙️ নতুন ভিডিও ফাইল তৈরি হচ্ছে...")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video, "-i", tts_audio,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", final_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৬. টেলিগ্রামে আপলোড
        await status_msg.edit_text("🚀 আপলোড হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption="🎉 ডাবিং সম্পন্ন হয়েছে!",
            supports_streaming=True
        )

    except Exception as e:
        await callback_query.message.reply_text(f"❌ এরর: {str(e)}")

    finally:
        for path in [input_video, extracted_audio, tts_audio, final_video]:
            if os.path.exists(path):
                os.remove(path)
        if user_id in user_data:
            del user_data[user_id]
        await status_msg.delete()

print("Bot is running...")
app.run()
