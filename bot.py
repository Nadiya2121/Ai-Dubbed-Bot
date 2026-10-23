import sys
import os
import time
import shutil
import stat
import tempfile
import traceback
import subprocess

# =====================================================================
# ১. স্বয়ংক্রিয় প্যাকেজ ইনস্টলার
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "SpeechRecognition>=3.10.0",
    "deep-translator>=1.11.4",
    "gTTS>=2.5.0",
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
from gtts import gTTS
import edge_tts
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
try:
    os.chmod(FFMPEG_PATH, os.stat(FFMPEG_PATH).st_mode | stat.S_IEXEC | 0o755)
except Exception:
    pass

app = Client("koyeb_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
# ৩. হাই-ডেফিনিশন ক্রিস্টাল ক্লিয়ার ডাবিং ইঞ্জিন
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

# 🧠 সম্পূর্ণ অডিও শুনে নিখুঁত অনুবাদ
def transcribe_and_translate_clean(wav_path, target_lang):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 250
    recognizer.dynamic_energy_threshold = True

    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)

    spoken_text = ""
    # হিন্দি, ইংরেজি, বাংলা বা উর্দু ক্রমানুসারে ট্রাই করবে
    for lang in ["hi-IN", "en-US", "bn-BD", "ur-PK"]:
        try:
            text = recognizer.recognize_google(audio_data, language=lang)
            if text and len(text.strip()) > 1:
                spoken_text = text.strip()
                break
        except Exception:
            continue

    if not spoken_text:
        return ""

    target_code = VOICE_MAP.get(target_lang, {}).get("code", "bn")
    try:
        translated_text = GoogleTranslator(source='auto', target=target_code).translate(spoken_text)
        return translated_text
    except Exception:
        return spoken_text

# 🎙️ প্রাকৃতিক ও স্পষ্ট স্টুডিও সাউন্ড জেনারেটর (কোনো বিকৃতি ছাড়া)
async def generate_clean_speech(text, lang_code, voice_name, output_file):
    # চেষ্টা ১: মাইক্রোসফট নিউরাল এআই ভয়েস
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(output_file)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 200:
            return
    except Exception:
        pass

    # চেষ্টা ২: গুগল হাই-কোয়ালিটি পরিষ্কার ভয়েস (কোনো রোবটিক বিকৃতি ছাড়া)
    temp_mp3 = output_file + "_temp.mp3"
    tts = gTTS(text=text, lang=lang_code, slow=False)
    tts.save(temp_mp3)

    # 44.1kHz হাই-ডেফিনিশন স্টুডিও কোয়ালিটিতে কনভার্ট করা (যাতে স্পষ্ট শোনা যায়)
    subprocess.run([
        FFMPEG_PATH, "-y", "-i", temp_mp3,
        "-ar", "44100", "-b:a", "128k",
        output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(temp_mp3):
        try:
            os.remove(temp_mp3)
        except Exception:
            pass

# 🎙️ ডায়ালগ জোড়া দিয়ে স্পষ্ট ডাবিং ট্র্যাক তৈরি
async def process_clean_dubbing(input_video, target_lang, output_audio, base_dir):
    # অডিওকে পরিচ্ছন্ন ৩০ সেকেন্ডের খণ্ডে ভাগ করা
    chunk_pattern = os.path.join(base_dir, "chunk_%03d.wav")
    subprocess.run([
        FFMPEG_PATH, "-y", "-i", input_video,
        "-f", "segment", "-segment_time", "30",
        "-vn", "-ar", "16000", "-ac", "1",
        chunk_pattern
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chunk_files = sorted([
        os.path.join(base_dir, f) for f in os.listdir(base_dir)
        if f.startswith("chunk_") and f.endswith(".wav")
    ])

    if not chunk_files:
        raise Exception("ভিডিওর অডিও প্রসেস করা যায়নি!")

    lang_info = VOICE_MAP.get(target_lang, VOICE_MAP["bn"])
    temp_tts_files = []
    translated_count = 0

    for idx, chunk in enumerate(chunk_files):
        translated = transcribe_and_translate_clean(chunk, target_lang)
        seg_output = os.path.join(base_dir, f"seg_{idx}.mp3")

        if translated.strip():
            translated_count += 1
            # ছেলে ও মেয়ের কণ্ঠ অদলবদল করা
            voice = lang_info["male"] if idx % 2 == 0 else lang_info["female"]
            await generate_clean_speech(translated, lang_info["code"], voice, seg_output)
        else:
            # কথা না থাকলে ব্যাকগ্রাউন্ড হালকা সাউন্ড রাখা
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", chunk,
                "-af", "volume=0.2",
                "-ar", "44100",
                seg_output
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        temp_tts_files.append(seg_output)
        if os.path.exists(chunk):
            os.remove(chunk)

    if translated_count == 0:
        raise Exception("ভিডিওতে কোনো মানুষের স্পষ্ট সংলাপ পাওয়া যায়নি! স্পষ্ট কণ্ঠের ভিডিও দিন।")

    # সব ডায়ালগ একত্র করা
    concat_list = os.path.join(base_dir, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for t_file in temp_tts_files:
            f.write(f"file '{t_file}'\n")

    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c:a", "aac", "-b:a", "128k", output_audio
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
    await message.reply_text("👋 স্বাগতম! যেকোনো ১ থেকে ৩ মিনিটের ভিডিও পাঠান, আমি স্পষ্ট ও সুন্দর কণ্ঠে বাংলায় ডাব করে দেব।")

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
        [InlineKeyboardButton("🇧🇩 বাংলা ডাবিং", callback_data="bn"),
         InlineKeyboardButton("🇮🇳 হিন্দি ডাবিং", callback_data="hi"),
         InlineKeyboardButton("🇺🇸 ইংরেজি ডাবিং", callback_data="en")]
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

        # ১. স্পষ্ট ডায়ালগ শুনে ডাবিং তৈরি
        await status_msg.edit_text("⚙️ [▰▰▰▱] ৬০%\n🔹 সংলাপ শনাক্ত ও স্পষ্ট কণ্ঠে ডাবিং তৈরি হচ্ছে...")
        await process_clean_dubbing(input_video, target_lang, dubbed_audio, base_dir)

        # ২. অরিজিনাল সাউন্ড সরিয়ে সম্পূর্ণ নতুন হাই-কোয়ালিটি কণ্ঠ ভিডিওর সাথে মেলানো
        await status_msg.edit_text("⚙️ [▰▰▰▰] ৯০%\n🔹 সম্পূর্ণ নতুন ডাব করা ভিডিও একত্র করা হচ্ছে...")
        
        if video_duration:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", dubbed_audio,
                "-filter_complex", f"[1:a]apad=whole_dur={video_duration}[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", input_video, "-i", dubbed_audio,
                "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                "-c:a", "aac", "-b:a", "128k",
                final_video
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৩. টেলিগ্রামে ভিডিও আপলোড
        await status_msg.edit_text("🚀 ভিডিও তৈরি সম্পন্ন! টেলিগ্রামে পাঠানো হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption=f"🎉 **{VOICE_MAP.get(target_lang, {}).get('name', '')} ডাবিং সফলভাবে সম্পন্ন হয়েছে!**",
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

print("🚀 ফাইনাল হাই-ডেফিনিশন ডাবিং বট চালু হয়েছে...")
app.run()
