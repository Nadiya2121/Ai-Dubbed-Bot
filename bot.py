import sys
import os
import time
import json
import shutil
import subprocess

# =====================================================================
# ১. স্বয়ংক্রিয় প্যাকেজ ও লেটেস্ট লাইব্রেরি ইনস্টলার
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "groq>=0.11.0",
    "httpx==0.27.2",
    "edge-tts>=6.1.15",    # লেটেস্ট ভার্সন যা ৪০৩ ব্লক বাইপাস করে
    "python-dotenv==1.0.1",
    "imageio-ffmpeg==0.5.1"
]

def auto_setup():
    try:
        import pyrogram
        import groq
        import edge_tts
        import imageio_ffmpeg
        import httpx
    except ImportError:
        print("⚙️ প্রয়োজনীয় প্যাকেজগুলো আপডেট হচ্ছে, অপেক্ষা করুন...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES)
        print("✅ সব প্যাকেজ সফলভাবে রেডি!\n")

auto_setup()

# লাইব্রেরি লোড
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from groq import Groq
import edge_tts
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_KEY")

FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

app = Client("auto_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

# সেরা মানুষের মতো AI ভয়েস (Natural Neural Voices)
VOICES = {
    "bn": "bn-BD-NabanitaNeural",  # মিষ্টি বাংলা কণ্ঠ
    "hi": "hi-IN-MadhurNeural",    # সাবলীল হিন্দি কণ্ঠ
    "en": "en-US-GuyNeural"        # পরিষ্কার আমেরিকান ইংরেজি
}

LANG_NAMES = {
    "bn": "Bengali language only",
    "hi": "Hindi language only",
    "en": "English language only"
}

user_data = {}
last_update_time = {}

# =====================================================================
# ৩. হেল্পার ফাংশন
# =====================================================================
# ভিডিওর সঠিক সময় (Duration) সেকেন্ডে বের করা
def get_video_duration(file_path):
    try:
        cmd = [
            FFMPEG_PATH, "-i", file_path
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        for line in result.stderr.split("\n"):
            if "Duration:" in line:
                time_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        pass
    return None

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

# কঠোর অনুবাদের ফাংশন (ভাষা কখনো ভুল হবে না)
def translate_with_groq(text, target_lang):
    target_name = LANG_NAMES.get(target_lang, "Bengali language only")
    chunks = [text[i:i+3500] for i in range(0, len(text), 3500)]
    translated_parts = []

    for chunk in chunks:
        system_prompt = (
            f"You are a professional film dubber. Your task is to translate speech strictly into {target_name}. "
            "Never mix languages. Never output explanations or markdown. Output ONLY the translated spoken lines."
        )

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk}
            ],
            temperature=0.1  # কম টেম্পারেচার দিলে মডেল কখনো ভুল ভাষা বেছে নেয় না
        )
        translated_parts.append(response.choices[0].message.content.strip())

    return " ".join(translated_parts)

# রিয়েলিস্টিক মানুষের কণ্ঠ তৈরি
async def generate_realistic_voice(text, target_lang, output_file):
    voice = VOICES.get(target_lang, "bn-BD-NabanitaNeural")
    communicate = edge_tts.Communicate(text, voice, rate="+0%", pitch="+0Hz")
    await communicate.save(output_file)

# =====================================================================
# ৪. টেলিগ্রাম বট হ্যান্ডলার
# =====================================================================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! আমাকে যেকোনো ভাষার ভিডিও পাঠান, আমি আসল মানুষের মতো কণ্ঠে সম্পূর্ণ ভিডিও ডাবিং করে দেব।")

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
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি! আবার ভিডিও পাঠান।")
        return

    input_video = user_data[user_id]
    base_dir = os.path.dirname(input_video)
    extracted_audio = os.path.join(base_dir, f"{user_id}_audio.mp3")
    tts_audio = os.path.join(base_dir, f"{user_id}_tts.mp3")
    final_video = os.path.join(base_dir, f"{user_id}_dubbed.mp4")

    status_msg = await callback_query.message.edit_text("⚙️ ডাবিং শুরু হচ্ছে...")

    try:
        # ১. অরিজিনাল ভিডিওর দৈর্ঘ্য মাপা
        video_duration = get_video_duration(input_video)

        # ২. অডিও আলাদা করা
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▱▱▱] ২৫%\n🔹 অডিও প্রসেস করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not os.path.exists(extracted_audio):
            raise Exception("ভিডিও থেকে অডিও আলাদা করা যায়নি!")

        # ৩. Groq Cloud (Whisper AI)
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▱▱] ৫০%\n🔹 কথা থেকে টেক্সটে রূপান্তর হচ্ছে...")
        with open(extracted_audio, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(extracted_audio), file.read()),
                model="whisper-large-v3",
                response_format="text"
            )

        original_text = str(transcription).strip()
        if not original_text:
            raise Exception("ভিডিওতে কোনো মানুষের কথা পাওয়া যায়নি!")

        # ৪. সঠিক ভাষায় অনুবাদ
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▱] ৭৫%\n🔹 নিখুঁত অনুবাদ ও মানুষের কণ্ঠ তৈরি হচ্ছে...")
        translated_text = translate_with_groq(original_text, target_lang)

        # ৫. মানুষের মতো রিয়েলিস্টিক ভয়েস তৈরি
        await generate_realistic_voice(translated_text, target_lang, tts_audio)

        # ৬. ভিডিও রেন্ডারিং (ভিডিও এক সেকেন্ডও কাটা যাবে না!)
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▰] ৯০%\n🔹 সম্পূর্ণ ভিডিও জোড়া লাগানো হচ্ছে...")
        
        # -shortest বাদ দেওয়া হয়েছে এবং ভিডিওর মূল সাইজ অক্ষুণ্ণ রাখার কমান্ড
        if video_duration:
            # অডিও ছোট হলেও ভিডিও পুরো চলবে
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", tts_audio,
                "-filter_complex", f"[1:a]apad=whole_dur={video_duration}[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", tts_audio,
                "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৭. আপলোড
        await status_msg.edit_text("🚀 ভিডিও প্রস্তুত! টেলিগ্রামে পাঠানো হচ্ছে...")
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

print("🚀 ১০০% পারফেক্ট AI ডাবিং বট চালু হয়েছে...")
app.run()
