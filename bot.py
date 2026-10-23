import sys
import os
import time
import json
import shutil
import asyncio
import subprocess

# =====================================================================
# ১. প্রয়োজনীয় প্যাকেজ ইনস্টল
# =====================================================================
REQUIRED_PACKAGES = [
    "pyrogram==2.0.106",
    "tgcrypto==1.2.5",
    "google-generativeai>=0.8.0",
    "edge-tts>=6.1.9",
    "python-dotenv==1.0.1",
    "imageio-ffmpeg==0.5.1"
]

def auto_setup():
    try:
        import pyrogram
        import google.generativeai
        import edge_tts
        import imageio_ffmpeg
    except ImportError:
        print("⚙️ প্রয়োজনীয় প্যাকেজ ইনস্টল হচ্ছে...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES)
        print("✅ ইনস্টল সম্পন্ন!\n")

auto_setup()

# লাইব্রেরি লোড
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai
import edge_tts
import imageio_ffmpeg

# =====================================================================
# ২. কনফিগারেশন
# =====================================================================
load_dotenv()

API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")

genai.configure(api_key=GEMINI_API_KEY)
FFMPEG_PATH = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

app = Client("koyeb_dub_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ভাষা ও নিখুঁত মানুষের নিউরাল ভয়েস ম্যাপিং (সম্পূর্ণ ফ্রি)
VOICE_MAP = {
    "bn": {
        "name": "Bengali (বাংলা)",
        "male": "bn-BD-PradeepNeural",     # চমৎকার পুরুষালী কণ্ঠ
        "female": "bn-BD-NabanitaNeural"   # মিষ্টি নারী কণ্ঠ
    },
    "hi": {
        "name": "Hindi (हिन्दी)",
        "male": "hi-IN-MadhurNeural",
        "female": "hi-IN-SwaraNeural"
    },
    "en": {
        "name": "English",
        "male": "en-US-ChristopherNeural",
        "female": "en-US-JennyNeural"
    }
}

user_data = {}
last_update_time = {}

# =====================================================================
# ৩. ডাবিং ইঞ্জিন ফাংশন
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

# 🧠 এআই দিয়ে ক্যারেক্টার ও ডায়ালগ অনুবাদ
def analyze_and_translate_audio(audio_path, target_lang):
    target_name = VOICE_MAP.get(target_lang, {}).get("name", "Bengali")
    
    gemini_file = genai.upload_file(path=audio_path)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    You are a professional film dubbing director. 
    Analyze the speech in this audio clip:
    1. Identify all speakers and classify each dialogue as 'male' or 'female'.
    2. Accurately translate their dialogues into {target_name}. 
    3. Make sure the translated lines sound completely natural for human speech.
    4. Return strictly a JSON array without markdown formatting:
    [
      {{"gender": "male", "text": "অনূদিত ডায়ালগ..."}},
      {{"gender": "female", "text": "অনূদিত ডায়ালগ..."}}
    ]
    """

    response = model.generate_content([gemini_file, prompt])
    text = response.text.strip()

    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        return json.loads(text.strip())
    except Exception:
        return [{"gender": "male", "text": text.replace('"', '').strip()}]

# 🎙️ একাধিক চরিত্রের জন্য হাই-কোয়ালিটি ভয়েস তৈরি
async def generate_multispeaker_audio(dialogues, target_lang, output_file, base_dir):
    temp_files = []
    lang_info = VOICE_MAP.get(target_lang, VOICE_MAP["bn"])

    for idx, item in enumerate(dialogues):
        gender = item.get("gender", "male").lower()
        dialogue_text = item.get("text", "")
        if not dialogue_text:
            continue

        seg_file = os.path.join(base_dir, f"seg_{idx}.mp3")
        voice_to_use = lang_info["female"] if "female" in gender else lang_info["male"]

        # ন্যাচারাল নিউরাল ভয়েসে ডাব তৈরি
        communicate = edge_tts.Communicate(dialogue_text, voice_to_use)
        await communicate.save(seg_file)
        temp_files.append(seg_file)

    if not temp_files:
        raise Exception("কোনো ডাবিং অডিও তৈরি হয়নি!")

    # অডিও ট্র্যাকগুলো জোড়া লাগানো
    concat_list = os.path.join(base_dir, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for t_file in temp_files:
            f.write(f"file '{t_file}'\n")

    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
    await message.reply_text("👋 স্বাগতম! ১ থেকে ৩ মিনিটের যেকোনো ভিডিও পাঠান, আমি ছেলে ও মেয়ের কণ্ঠ আলাদা করে সম্পূর্ণ ডাব করে দেব।")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    file = message.video or message.document
    if not file.file_name and not message.video:
        return

    msg = await message.reply_text("⏳ ভিডিও ডাউনলোড হচ্ছে...")
    user_id = str(message.from_user.id)
    target_path = os.path.abspath(f"{user_id}_input.mp4")

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
    await msg.edit_text("✅ ডাউনলোড সম্পূর্ণ!\nকোন ভাষায় ডাব করতে চান সিলেক্ট করুন:", reply_markup=markup)

@app.on_callback_query()
async def process_dubbing(client, callback_query):
    user_id = str(callback_query.from_user.id)
    target_lang = callback_query.data

    if user_id not in user_data:
        await callback_query.message.edit_text("❌ ফাইল পাওয়া যায়নি! দয়া করে আবার ভিডিও পাঠান।")
        return

    input_video = user_data[user_id]
    base_dir = os.path.dirname(input_video)
    extracted_audio = os.path.join(base_dir, f"{user_id}_extracted.mp3")
    dubbed_audio = os.path.join(base_dir, f"{user_id}_dubbed_audio.mp3")
    final_video = os.path.join(base_dir, f"{user_id}_final_dubbed.mp4")

    status_msg = await callback_query.message.edit_text("⚙️ **ডাবিং প্রক্রিয়া শুরু হচ্ছে...**")

    try:
        video_duration = get_media_duration(input_video)

        # ১. ভিডিও থেকে অডিও নিষ্কাশন
        await status_msg.edit_text("⚙️ [▰▱▱▱] ২৫%\n🔹 অডিও আলাদা করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ২. চরিত্র বিশ্লেষণ ও ডায়ালগ রূপান্তর
        await status_msg.edit_text("⚙️ [▰▰▱▱] ৫০%\n🔹 চরিত্র ও সংলাপ বিশ্লেষণ করা হচ্ছে...")
        dialogues = analyze_and_translate_audio(extracted_audio, target_lang)

        # ৩. চরিত্র অনুযায়ী মানুষের কণ্ঠে ডাবিং তৈরি
        await status_msg.edit_text("⚙️ [▰▰▰▱] ৭৫%\n🔹 ছেলে ও মেয়ের কণ্ঠে নতুন ডাব রেন্ডার হচ্ছে...")
        await generate_multispeaker_audio(dialogues, target_lang, dubbed_audio, base_dir)

        # ৪. অরিজিনাল ভিডিওর সাথে নতুন ভয়েস নিখুঁতভাবে টাইমিং ম্যাচ করে জোড়া লাগানো
        await status_msg.edit_text("⚙️ [▰▰▰▰] ৯০%\n🔹 সম্পূর্ণ ডাব করা ভিডিও একত্র করা হচ্ছে...")
        
        # টাইমিং ফিট করা (ভিডিওর সমান অডিও বানানো)
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

        # ৫. টেলিগ্রামে ভিডিও পাঠানো
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
        await callback_query.message.reply_text(f"❌ এরর: {str(e)}")

    finally:
        # ফাইল পরিষ্কার করা যাতে Koyeb সার্ভার জ্যাম না হয়
        for path in [input_video, extracted_audio, dubbed_audio, final_video]:
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

print("🚀 ডাবিং বট চালু হয়েছে...")
app.run()
