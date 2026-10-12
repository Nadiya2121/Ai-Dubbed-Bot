import sys
import os
import time
import shutil
import subprocess

# =====================================================================
# ১. স্বয়ংক্রিয় প্যাকেজ ও FFmpeg ইনস্টলার (Auto-Installer)
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "groq>=0.11.0",
    "httpx==0.27.2",
    "edge-tts>=6.1.12",
    "gtts>=2.5.0",
    "python-dotenv==1.0.1",
    "imageio-ffmpeg==0.5.1"
]

def auto_setup():
    try:
        import pyrogram
        import groq
        import edge_tts
        import gtts
        import imageio_ffmpeg
        import httpx
    except ImportError:
        print("⚙️ প্রয়োজনীয় প্যাকেজ ইনস্টল হচ্ছে, অপেক্ষা করুন...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + REQUIRED_PACKAGES)
        print("✅ সব প্যাকেজ ইনস্টল সম্পন্ন হয়েছে!\n")

auto_setup()

# লাইব্রেরি লোড করা
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
from gtts import gTTS
import edge_tts
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))                  # আপনার API ID দিন
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")              # আপনার API HASH দিন
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")           # আপনার BOT TOKEN দিন
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_KEY")     # আপনার GROQ KEY দিন

# স্বয়ংক্রিয় FFmpeg পাথ
FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

app = Client("auto_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

VOICES = {
    "bn": "bn-BD-NabanitaNeural",  # বাংলা
    "hi": "hi-IN-MadhurNeural",    # হিন্দি
    "en": "en-US-GuyNeural"        # ইংরেজি
}

LANG_NAMES = {
    "bn": "Bengali (বাংলা)",
    "hi": "Hindi (हिन्दी)",
    "en": "English"
}

user_data = {}
last_update_time = {}

# =====================================================================
# ৩. হেল্পার ফাংশন (লাইভ প্রগ্রেস বার, AI অনুবাদ ও নিরাপদ ভয়েস ইঞ্জিন)
# =====================================================================
async def progress_bar(current, total, message, action_name):
    now = time.time()
    msg_id = message.id

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

# আনলিমিটেড AI অনুবাদ (Auto-Fallback)
def translate_with_groq(text, target_lang):
    target_name = LANG_NAMES.get(target_lang, "Bengali")
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    translated_parts = []

    models_to_try = [
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]

    for chunk in chunks:
        prompt = (
            f"You are a professional video dubbing translator.\n"
            f"Translate the following speech naturally and accurately into {target_name}.\n"
            f"Rules:\n"
            f"1. Make the translation sound like natural spoken language for dubbing.\n"
            f"2. Return ONLY the translated text. Do not add explanations, notes, or quotes.\n\n"
            f"Original Text:\n{chunk}"
        )
        
        translated_chunk = None
        for model_name in models_to_try:
            try:
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                translated_chunk = response.choices[0].message.content.strip()
                if translated_chunk:
                    break
            except Exception:
                continue

        if not translated_chunk:
            translated_chunk = chunk

        translated_parts.append(translated_chunk)

    return " ".join(translated_parts)

# 🎙️ নিরাপদ ডুয়েল ভয়েস ইঞ্জিন (Edge-TTS + Google TTS Fallback)
async def generate_speech_safe(text, target_lang, output_file):
    # ১ম চেষ্টা: Microsoft Edge-TTS (উচ্চ কোয়ালিটি)
    try:
        voice = VOICES.get(target_lang, "bn-BD-NabanitaNeural")
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 100:
            return
    except Exception:
        pass

    # ২য় চেষ্টা: Google TTS (ক্লাউড ব্লক এড়াতে ১০০% গ্যারান্টি ব্যাকআপ)
    loop = asyncio.get_event_loop()
    def run_gtts():
        tts = gTTS(text=text, lang=target_lang, slow=False)
        tts.save(output_file)

    await loop.run_in_executor(None, run_gtts)

# =====================================================================
# ৪. টেলিগ্রাম বট হ্যান্ডলার
# =====================================================================
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
    target_path = os.path.abspath(f"{user_id}_input.mp4")

    downloaded_path = await client.download_media(
        message, 
        file_name=target_path,
        progress=progress_bar,
        progress_args=(msg, "ভিডিও ডাউনলোড হচ্ছে")
    )
    user_data[user_id] = os.path.abspath(downloaded_path)

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
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি! আবার নতুন করে ভিডিও পাঠান।")
        return

    input_video = user_data[user_id]
    base_dir = os.path.dirname(input_video)
    extracted_audio = os.path.join(base_dir, f"{user_id}_audio.mp3")
    tts_audio = os.path.join(base_dir, f"{user_id}_tts.mp3")
    final_video = os.path.join(base_dir, f"{user_id}_dubbed.mp4")

    status_msg = await callback_query.message.edit_text("⚙️ ডাবিং শুরু হচ্ছে...")

    try:
        # ১. অডিও আলাদা করা
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▱▱▱] ২৫%\n🔹 অডিও আলাদা ও অপ্টিমাইজ করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not os.path.exists(extracted_audio):
            raise Exception("ভিডিও থেকে অডিও আলাদা করা যায়নি! ভিডিওতে কি সাউন্ড আছে?")

        # ২. Groq Cloud (Whisper AI)
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▱▱] ৫০%\n🔹 কথা থেকে টেক্সটে রূপান্তর হচ্ছে (Whisper AI)...")
        with open(extracted_audio, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(extracted_audio), file.read()),
                model="whisper-large-v3",
                response_format="text"
            )

        original_text = str(transcription).strip()
        if not original_text:
            raise Exception("ভিডিওতে কোনো মানুষের কথা শনাক্ত করা যায়নি!")

        # ৩. Groq AI অনুবাদ
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▱] ৭৫%\n🔹 AI অনুবাদ ও নতুন কণ্ঠ তৈরি হচ্ছে...")
        translated_text = translate_with_groq(original_text, target_lang)

        # ৪. সুরক্ষিত ডুয়েল ভয়েস ইঞ্জিন
        await generate_speech_safe(translated_text, target_lang, tts_audio)

        # ৫. ভিডিও রেন্ডারিং
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▰] ৯০%\n🔹 ভিডিও প্রস্তুত করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video, "-i", tts_audio,
            "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", final_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৬. টেলিগ্রামে আপলোড
        await status_msg.edit_text("🚀 ভিডিও তৈরি শেষ! টেলিগ্রামে পাঠানো হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption=f"🎉 **ডাবিং সফলভাবে সম্পন্ন হয়েছে!**\n\n🗣️ **অনূদিত রূপ:**\n{translated_text[:300]}...",
            supports_streaming=True,
            progress=progress_bar,
            progress_args=(status_msg, "ভিডিও আপলোড হচ্ছে")
        )

    except Exception as e:
        await callback_query.message.reply_text(f"❌ এরর: {str(e)}")

    finally:
        # সার্ভার ক্লিনআপ
        for path in [input_video, extracted_audio, tts_audio, final_video]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        if user_id in user_data:
            del user_data[user_id]
        try:
            await status_msg.delete()
        except Exception:
            pass

print("🚀 ফাইনাল AI ডাবিং বট সফলভাবে চালু হয়েছে...")
app.run()
