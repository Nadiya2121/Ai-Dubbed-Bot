import sys
import os
import time
import json
import shutil
import subprocess

# =====================================================================
# ১. স্বয়ংক্রিয় প্যাকেজ ইনস্টলার (Google AI Studio সহ)
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "google-generativeai>=0.8.0",
    "gtts>=2.5.0",
    "python-dotenv==1.0.1",
    "imageio-ffmpeg==0.5.1"
]

def auto_setup():
    try:
        import pyrogram
        import google.generativeai
        import gtts
        import imageio_ffmpeg
    except ImportError:
        print("⚙️ Google AI Studio প্যাকেজগুলো ইনস্টল হচ্ছে, অপেক্ষা করুন...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES)
        print("✅ সব প্যাকেজ ইনস্টল সম্পন্ন হয়েছে!\n")

auto_setup()

# লাইব্রেরি লোড
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai
from gtts import gTTS
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")  # aistudio.google.com এর কী

# Google Gemini কনফিগার
genai.configure(api_key=GEMINI_API_KEY)

FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

app = Client("gemini_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

LANG_NAMES = {
    "bn": "Bengali (বাংলা)",
    "hi": "Hindi (हिन्दी)",
    "en": "English"
}

user_data = {}
last_update_time = {}

# =====================================================================
# ৩. হেল্পার ফাংশন
# =====================================================================
def get_video_duration(file_path):
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

# 🧠 Google Gemini 1.5 দিয়ে মাল্টি-স্পিকার শনাক্ত ও অনুবাদ
def analyze_and_translate_with_gemini(audio_path, target_lang):
    target_name = LANG_NAMES.get(target_lang, "Bengali")

    # অডিও ফাইল সরাসরি জেমিনিতে আপলোড
    gemini_file = genai.upload_file(path=audio_path)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    You are an expert film dubber. Listen to this audio carefully:
    1. Identify all speakers and determine their gender ('male' or 'female').
    2. Translate their spoken dialogues strictly into {target_name}. Keep it natural for spoken speech.
    3. Return ONLY a valid JSON list without any extra text or markdown formatting:
    [
      {{"gender": "male", "text": "translated dialogue..."}},
      {{"gender": "female", "text": "translated dialogue..."}}
    ]
    """

    response = model.generate_content([gemini_file, prompt])
    text = response.text.strip()

    # JSON ক্লিনিং
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    try:
        return json.loads(text.strip())
    except Exception:
        # ব্যাকআপ যদি সরাসরি টেক্সট দেয়
        return [{"gender": "male", "text": text.replace('"', '').strip()}]

# 🎙️ ছেলে ও মেয়ের আলাদা কণ্ঠ তৈরি
def generate_multispeaker_audio(dialogues, target_lang, output_file, base_dir):
    temp_files = []
    
    for idx, item in enumerate(dialogues):
        gender = item.get("gender", "male").lower()
        dialogue_text = item.get("text", "")
        if not dialogue_text:
            continue

        raw_tts_file = os.path.join(base_dir, f"seg_{idx}_raw.mp3")
        final_seg_file = os.path.join(base_dir, f"seg_{idx}.mp3")

        # বেস ভয়েস তৈরি
        tts = gTTS(text=dialogue_text, lang=target_lang, slow=False)
        tts.save(raw_tts_file)

        # 🎭 ছেলেদের জন্য গম্ভীর পুরুষালি কণ্ঠ, মেয়েদের জন্য মিষ্টি নারী কণ্ঠ
        if "male" in gender:
            # পিচ নামিয়ে পুরুষের ভরাট কণ্ঠ করা
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", raw_tts_file,
                "-af", "asetrate=24000*0.82,atempo=1.22,bass=g=4",
                final_seg_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # স্বাভাবিক নারী কণ্ঠ
            subprocess.run([
                FFMPEG_PATH, "-y", "-i", raw_tts_file,
                "-af", "asetrate=24000*1.05,atempo=0.95",
                final_seg_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        temp_files.append(final_seg_file)
        if os.path.exists(raw_tts_file):
            os.remove(raw_tts_file)

    # সব সংলাপ জোড়া দিয়ে একটি ফুল অডিও ট্র্যাক বানানো
    concat_list = os.path.join(base_dir, "concat_list.txt")
    with open(concat_list, "w") as f:
        for t_file in temp_files:
            f.write(f"file '{t_file}'\n")

    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ক্লিনআপ
    for t_file in temp_files:
        if os.path.exists(t_file):
            os.remove(t_file)
    if os.path.exists(concat_list):
        os.remove(concat_list)

# =====================================================================
# ৪. টেলিগ্রাম বট হ্যান্ডলার
# =====================================================================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! আমি Google AI Studio চালিত মাল্টি-ভয়েস ডাবিং বট।\nভিডিও পাঠান, আমি ছেলে ও মেয়ের আলাদা আলাদা কণ্ঠে ডাব করে দেব।")

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
        # ১. অরিজিনাল ভিডিওর দৈর্ঘ্য জানা
        video_duration = get_video_duration(input_video)

        # ২. অডিও আলাদা করা
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▱▱▱] ২৫%\n🔹 অডিও প্রসেস করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ৩. Google Gemini 1.5 দিয়ে ছেলে/মেয়ে চরিত্র ও সংলাপ শনাক্ত
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▱▱] ৫০%\n🔹 Google AI চরিত্র ও ভাষা বিশ্লেষণ করছে...")
        dialogues = analyze_and_translate_with_gemini(extracted_audio, target_lang)

        # ৪. ছেলে ও মেয়ের আলাদা কণ্ঠে অডিও তৈরি
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▱] ৭৫%\n🔹 ছেলে ও মেয়ের আলাদা কণ্ঠে ডাবিং তৈরি হচ্ছে...")
        generate_multispeaker_audio(dialogues, target_lang, tts_audio, base_dir)

        # ৫. সম্পূর্ণ ভিডিও রেন্ডারিং
        await status_msg.edit_text("⚙️ **ডাবিং প্রসেসিং:**\n\n[▰▰▰▰] ৯০%\n🔹 সম্পূর্ণ ভিডিও জোড়া লাগানো হচ্ছে...")
        if video_duration:
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

        # ৬. টেলিগ্রামে আপলোড
        await status_msg.edit_text("🚀 ভিডিও প্রস্তুত! টেলিগ্রামে পাঠানো হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption="🎉 **Google AI Studio দ্বারা মাল্টি-ভয়েস ডাবিং সম্পন্ন হয়েছে!**",
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

print("🚀 Google AI Studio চালিত মাল্টি-ভয়েস ডাবিং বট চালু হয়েছে...")
app.run()
