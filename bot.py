import sys
import os
import time
import shutil
import stat
import tempfile
import traceback
import subprocess

# =====================================================================
# ১. স্বয়ংক্রিয় প্যাকেজ ইনস্টলার (Gemini ছাড়া সম্পূর্ণ ফ্রি ইঞ্জিন)
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "SpeechRecognition>=3.10.0",
    "deep-translator>=1.11.4",
    "edge-tts>=6.1.9",
    "python-dotenv==1.0.1",
    "imageio-ffmpeg==0.5.1"
]

def auto_setup():
    needed = []
    for pkg in REQUIRED_PACKAGES:
        pkg_name = pkg.split("==")[0].split(">=")[0].replace("-", "_")
        try:
            __import__(pkg_name)
        except ImportError:
            needed.append(pkg)
    
    if needed:
        print("⚙️ প্রয়োজনীয় প্যাকেজগুলো ইনস্টল হচ্ছে...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES)
        print("✅ সব প্যাকেজ ইনস্টল সম্পন্ন হয়েছে!\n")

auto_setup()

# লাইব্রেরি লোড
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import speech_recognition as sr
from deep_translator import GoogleTranslator
import edge_tts
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন (কোনো Gemini API Key লাগবে না!)
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# FFmpeg পারমিশন ফিক্স
FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(FFMPEG_PATH, os.stat(FFMPEG_PATH).st_mode | stat.S_IEXEC | 0o755)
except Exception:
    pass

app = Client("koyeb_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ভাষা ও প্রাকৃতিক এআই নিউরাল কণ্ঠ
VOICE_MAP = {
    "bn": {
        "name": "Bengali (বাংলা)",
        "code": "bn",
        "male": "bn-BD-PradeepNeural",
        "female": "bn-BD-NabanitaNeural"
    },
    "hi": {
        "name": "Hindi (हिन्दी)",
        "code": "hi",
        "male": "hi-IN-MadhurNeural",
        "female": "hi-IN-SwaraNeural"
    },
    "en": {
        "name": "English",
        "code": "en",
        "male": "en-US-ChristopherNeural",
        "female": "en-US-JennyNeural"
    }
}

user_data = {}
last_update_time = {}
TEMP_DIR = tempfile.gettempdir()

# =====================================================================
# ৩. সম্পূর্ণ অটোমেটিক ডাবিং ইঞ্জিন (Zero API Key Pipeline)
# =====================================================================
def get_media_duration(file_path):
    try:
        cmd = [FFMPEG_PATH, "-i", file_path]
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
    bar = "▰" * int((current / total) * 10) + "▱" * (10 - int((current / total) * 10))

    try:
        await message.edit_text(
            f"⏳ **{action_name}...**\n\n[{bar}] {percentage:.1f}%\n"
            f"📊 সাইজ: {current / (1024*1024):.1f} MB / {total / (1024*1024):.1f} MB"
        )
    except Exception:
        pass

# 🧠 সরাসরি ফ্রি ভয়েস-টু-টেক্সট ও অনুবাদ ইঞ্জিন
def transcribe_and_translate_auto(wav_path, target_lang):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)

    # ১. ফ্রি গুগল স্পিচ দিয়ে কথা লেখায় রূপান্তর
    spoken_text = ""
    try:
        spoken_text = recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        pass  # কোনো কথা না থাকলে বা শুধু মিউজিক থাকলে সমস্যা নেই
    except Exception:
        pass

    if not spoken_text.strip():
        return ""

    # ২. ফ্রি ডিপ ট্রান্সলেটর দিয়ে লক্ষ্য ভাষায় অনুবাদ
    lang_code = VOICE_MAP.get(target_lang, {}).get("code", "bn")
    try:
        translated_text = GoogleTranslator(source='auto', target=lang_code).translate(spoken_text)
        return translated_text
    except Exception:
        return spoken_text

# 🎙️ একাধিক খণ্ডে ভাগ করে অটোমেটিক জীবন্ত কণ্ঠে ডাব তৈরি
async def process_multispeaker_dubbing(input_video, target_lang, output_audio, base_dir):
    # ১. অডিওকে নিখুঁত টাইমিং অনুযায়ী ১৫ সেকেন্ডের ছোট ছোট ডায়ালগ পার্টে ভাগ করা
    chunk_pattern = os.path.join(base_dir, "chunk_%03d.wav")
    subprocess.run([
        FFMPEG_PATH, "-y", "-i", input_video,
        "-f", "segment", "-segment_time", "15",
        "-vn", "-ar", "16000", "-ac", "1",
        chunk_pattern
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chunk_files = sorted([
        os.path.join(base_dir, f) for f in os.listdir(base_dir)
        if f.startswith("chunk_") and f.endswith(".wav")
    ])

    if not chunk_files:
        raise Exception("ভিডিওর অডিও ট্র্যাক প্রসেস করা সম্ভব হয়নি!")

    lang_info = VOICE_MAP.get(target_lang, VOICE_MAP["bn"])
    temp_tts_files = []

    # ২. প্রতি টুকরো অডিও শুনে অনুবাদ করে ছেলে ও মেয়ের মিষ্টি কণ্ঠে তৈরি
    for idx, chunk in enumerate(chunk_files):
        translated = transcribe_and_translate_auto(chunk, target_lang)
        seg_output = os.path.join(base_dir, f"seg_{idx}.mp3")

        # ডায়ালগ থাকলে ছেলে ও মেয়ের কণ্ঠ অদলবদল করে ন্যাচারাল ডাবিং দেওয়া
        if translated.strip():
            voice = lang_info["male"] if idx % 2 == 0 else lang_info["female"]
            communicate = edge_tts.Communicate(translated, voice)
            await communicate.save(seg_output)
        else:
            # ডায়ালগ না থাকলে (মিউজিক বা নীরবতা) অরিজিনাল অডিওকে হালকা সাউন্ডে রাখা
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", chunk,
                "-af", "volume=0.3",
                seg_output
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        temp_tts_files.append(seg_output)
        if os.path.exists(chunk):
            os.remove(chunk)

    # ৩. সব খণ্ড নিখুঁতভাবে একসাথে জোড়া লাগানো
    concat_list = os.path.join(base_dir, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for t_file in temp_tts_files:
            f.write(f"file '{t_file}'\n")

    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", output_audio
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for t_file in temp_tts_files:
        if os.path.exists(t_file):
            os.remove(t_file)
    if os.path.exists(concat_list):
        os.remove(concat_list)

# =====================================================================
# ৪. টেলিগ্রাম বট হ্যান্ডলার
# =====================================================================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! যেকোনো ১ থেকে ৩ মিনিটের ভিডিও পাঠান, কোনো এরর বা ঝামেলা ছাড়াই সম্পূর্ণ স্বয়ংক্রিয়ভাবে ডাব করে দেব।")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    file = message.video or message.document
    if not file.file_name and not message.video:
        return

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে...")
    user_id = str(message.from_user.id)
    target_path = os.path.join(TEMP_DIR, f"{user_id}_input.mp4")

    downloaded_path = await client.download_media(
        message, 
        file_name=target_path,
        progress=progress_bar,
        progress_args=(msg, "ডাউনলোড চলছে")
    )
    user_data[user_id] = os.path.abspath(downloaded_path)

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="bn"),
         InlineKeyboardButton("🇮🇳 হিন্দি", callback_data="hi"),
         InlineKeyboardButton("🇺🇸 ইংরেজি", callback_data="en")]
    ])
    await msg.edit_text("✅ ডাউনলোড সম্পন্ন!\nকোন ভাষায় ডাব করতে চান সিলেক্ট করুন:", reply_markup=markup)

@app.on_callback_query()
async def process_dubbing(client, callback_query):
    user_id = str(callback_query.from_user.id)
    target_lang = callback_query.data

    if user_id not in user_data:
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি! দয়া করে আবার ভিডিও পাঠান।")
        return

    input_video = user_data[user_id]
    base_dir = TEMP_DIR
    dubbed_audio = os.path.join(base_dir, f"{user_id}_dubbed.mp3")
    final_video = os.path.join(base_dir, f"{user_id}_final_dubbed.mp4")

    status_msg = await callback_query.message.edit_text("⚙️ **ডাবিং প্রক্রিয়া শুরু হচ্ছে...**")

    try:
        video_duration = get_media_duration(input_video)

        # ১. স্বয়ংক্রিয়ভাবে কথা শুনে ও অনুবাদ করে ভয়েস তৈরি (Gemini ছাড়া)
        await status_msg.edit_text("⚙️ [▰▰▰▱] ৬০%\n🔹 কথা বিশ্লেষণ ও নতুন কণ্ঠ তৈরি হচ্ছে...")
        await process_multispeaker_dubbing(input_video, target_lang, dubbed_audio, base_dir)

        # ২. ভিডিওর সাথে নিখুঁতভাবে টাইমিং সিঙ্ক করে জোড়া লাগানো
        await status_msg.edit_text("⚙️ [▰▰▰▰] ৯০%\n🔹 সম্পূর্ণ ডাব করা ভিডিও একত্র করা হচ্ছে...")
        
        if video_duration:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", dubbed_audio,
                "-filter_complex", f"[1:a]apad=whole_dur={video_duration}[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", dubbed_audio,
                "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৩. টেলিগ্রামে ভিডিও আপলোড
        await status_msg.edit_text("🚀 ভিডিও তৈরি সম্পন্ন! টেলিগ্রামে পাঠানো হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption=f"🎉 **{VOICE_MAP.get(target_lang, {}).get('name', '')} ডাবিং সম্পন্ন হয়েছে!**",
            supports_streaming=True,
            progress=progress_bar,
            progress_args=(status_msg, "ভিডিও আপলোড হচ্ছে")
        )

    except Exception as e:
        print(f"ERROR OCCURRED:\n{traceback.format_exc()}")
        await callback_query.message.reply_text(f"❌ এরর হয়েছে:\n`{str(e)}`")

    finally:
        for path in [input_video, dubbed_audio, final_video]:
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

print("🚀 ১০০% অটোমেটিক জেমিনি-মুক্ত ডাবিং বট চালু হয়েছে...")
app.run()
