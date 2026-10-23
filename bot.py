import sys
import os
import time
import json
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
    "groq>=0.11.0",
    "edge-tts>=6.1.9",
    "gTTS>=2.5.0",
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
from groq import Groq
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

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
        "male": "bn-BD-PradeepNeural",     # গম্ভীর পুরুষ কণ্ঠ
        "female": "bn-BD-NabanitaNeural"   # মিষ্টি নারী কণ্ঠ
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
# ৩. মাল্টি-ক্যারেক্টার ডাবিং ইঞ্জিন (ছেলে ও মেয়ের আলাদা সংলাপ)
# =====================================================================
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

# 🧠 ছেলে ও মেয়ের চরিত্র আলাদা করে সংলাপ অনুবাদ করা
def transcribe_and_split_dialogues(audio_path, target_lang):
    if not GROQ_API_KEY:
        raise Exception("GROQ_API_KEY পাওয়া যায়নি! Koyeb-এ GROQ_API_KEY যোগ করুন।")

    client = Groq(api_key=GROQ_API_KEY)

    # ১. Whisper দিয়ে আসল কথোপকথন নির্ভুলভাবে শোনা
    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f.read()),
            model="whisper-large-v3",
            response_format="text"
        )

    full_transcript = str(transcription).strip()
    if not full_transcript or len(full_transcript) < 2:
        raise Exception("ভিডিওতে কোনো মানুষের স্পষ্ট কথা খুঁজে পাওয়া যায়নি!")

    target_name = VOICE_MAP.get(target_lang, {}).get("name", "Bengali")

    # ২. LLaMA 3.3 দিয়ে চরিত্র অনুযায়ী সংলাপ ভাগ করা (ছেলে vs মেয়ে)
    prompt = f"""
    You are an expert film dubbing director.
    Analyze the full transcript of this video which may contain multiple characters (male, female, or narrator):
    "{full_transcript}"

    Instructions:
    1. Break down the scene line-by-line into individual dialogue turns.
    2. Identify who is speaking each line: determine the gender ('male' or 'female') of the speaker.
    3. Translate each dialogue naturally into spoken, dramatic, colloquial {target_name}.
    4. Return STRICTLY a JSON object with a list named "dialogues":
    {{
      "dialogues": [
        {{"gender": "male", "text": "সংলাপ..."}},
        {{"gender": "female", "text": "সংলাপ..."}}
      ]
    }}
    """

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    result_json = json.loads(chat_completion.choices[0].message.content)
    dialogues = result_json.get("dialogues", [])

    if not dialogues:
        dialogues = [{"gender": "female", "text": full_transcript}]

    return dialogues

# 🎙️ ছেলে ও মেয়ের কণ্ঠ তৈরি করা
async def generate_character_voice(text, lang_code, voice_name, output_file, is_male=False):
    # চেষ্টা ১: মাইক্রোসফট নিউরাল ভয়েস
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(output_file)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 200:
            return
    except Exception:
        pass

    # চেষ্টা ২: গুগল হাই-কোয়ালিটি স্টুডিও ভয়েস
    raw_mp3 = output_file + "_raw.mp3"
    tts = gTTS(text=text, lang=lang_code, slow=False)
    tts.save(raw_mp3)

    subprocess.run([
        FFMPEG_PATH, "-y", "-i", raw_mp3,
        "-ar", "44100", "-ac", "2", "-b:a", "128k",
        output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(raw_mp3):
        try:
            os.remove(raw_mp3)
        except Exception:
            pass

# 🎙️ একাধিক চরিত্রের সব সংলাপ একত্র করা
async def render_multicharacter_dubbing(dialogues, target_lang, output_audio, base_dir):
    lang_info = VOICE_MAP.get(target_lang, VOICE_MAP["bn"])
    temp_files = []

    for idx, item in enumerate(dialogues):
        gender = item.get("gender", "male").lower()
        dialogue_text = item.get("text", "").strip()
        if not dialogue_text:
            continue

        seg_file = os.path.join(base_dir, f"dialogue_{idx}.mp3")
        is_male = ("male" in gender and "female" not in gender)
        
        # চরিত্র ছেলে হলে ছেলের কণ্ঠ, মেয়ে হলে মেয়ের কণ্ঠ
        voice_to_use = lang_info["male"] if is_male else lang_info["female"]

        await generate_character_voice(dialogue_text, lang_info["code"], voice_to_use, seg_file, is_male)
        temp_files.append(seg_file)

    if not temp_files:
        raise Exception("কোনো ডায়ালগ অডিও তৈরি হয়নি!")

    # সব সংলাপ একসাথে জোড়া লাগানো
    concat_list = os.path.join(base_dir, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for t_file in temp_files:
            f.write(f"file '{t_file}'\n")

    subprocess.run([
        FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-ar", "44100", "-ac", "2", "-b:a", "128k",
        output_audio
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for t_file in temp_files:
        if os.path.exists(t_file):
            try:
                os.remove(t_file)
            except Exception:
                pass
    if os.path.exists(concat_list):
        try:
            os.remove(concat_list)
        except Exception:
            pass

# =====================================================================
# ৪. টেলিগ্রাম বট হ্যান্ডলার
# =====================================================================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 স্বাগতম! ছেলে ও মেয়ে উভয়ের কথোপকথন আছে এমন যেকোনো ভিডিও পাঠান, আমি ছেলে ও মেয়ের আলাদা আলাদা কণ্ঠে সম্পূর্ণ সিনেমা স্টাইলে ডাব করে দেব।")

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
    extracted_audio = os.path.join(base_dir, f"{user_id}_extracted.mp3")
    dubbed_audio = os.path.join(base_dir, f"{user_id}_dubbed.mp3")
    final_video = os.path.join(base_dir, f"{user_id}_final_dubbed.mp4")

    status_msg = await callback_query.message.edit_text("⚙️ **ডাবিং প্রক্রিয়া শুরু হচ্ছে...**")

    try:
        # ১. অডিও আলাদা করা
        await status_msg.edit_text("⚙️ [▰▱▱▱] ২৫%\n🔹 অডিও আলাদা করা হচ্ছে...")
        subprocess.run([
            FFMPEG_PATH, "-y", "-i", input_video,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            extracted_audio
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ২. Whisper ও LLaMA 3.3 দিয়ে ছেলে ও মেয়ের সংলাপ আলাদা করা
        await status_msg.edit_text("⚙️ [▰▰▰▱] ৬০%\n🔹 Whisper AI ছেলে ও মেয়ের সংলাপ শনাক্ত করছে...")
        loop = asyncio.get_running_loop()
        dialogues = await loop.run_in_executor(
            None, transcribe_and_split_dialogues, extracted_audio, target_lang
        )

        # ৩. ছেলে ও মেয়ের কণ্ঠে সিনেমা কোয়ালিটি ডাবিং রেন্ডার করা
        await status_msg.edit_text("⚙️ [▰▰▰▰] ৮০%\n🔹 ছেলে ও মেয়ের আলাদা আলাদা কণ্ঠে ডাবিং তৈরি হচ্ছে...")
        await render_multicharacter_dubbing(dialogues, target_lang, dubbed_audio, base_dir)

        # ৪. ভিডিও একত্র করা
        await status_msg.edit_text("⚙️ [▰▰▰▰] ৯৫%\n🔹 ভিডিও একত্র করা হচ্ছে...")
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_video,
            "-i", dubbed_audio,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            final_video
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not os.path.exists(final_video) or os.path.getsize(final_video) == 0:
            raise Exception("ভিডিও রেন্ডারিং সম্পন্ন হয়নি!")

        # ৫. ডায়ালগের প্রিভিউ তৈরি
        preview_text = ""
        for d in dialogues[:3]:
            icon = "👨" if "male" in d.get("gender", "") and "female" not in d.get("gender", "") else "👩"
            preview_text += f"{icon} {d.get('text', '')}\n"

        # ৬. টেলিগ্রামে ভিডিও আপলোড
        await status_msg.edit_text("🚀 ভিডিও তৈরি সম্পন্ন! টেলিগ্রামে পাঠানো হচ্ছে...")
        await client.send_video(
            chat_id=callback_query.message.chat.id,
            video=final_video,
            caption=(
                f"🎉 **{VOICE_MAP.get(target_lang, {}).get('name', '')} মাল্টি-ভয়েস ডাবিং সম্পন্ন!**\n\n"
                f"🎭 **চরিত্রভিত্তিক সংলাপ:**\n{preview_text}"
            ),
            supports_streaming=True,
            progress=progress_bar,
            progress_args=(status_msg, "ভিডিও আপলোড হচ্ছে")
        )

    except Exception as e:
        print(f"ERROR OCCURRED:\n{traceback.format_exc()}")
        await callback_query.message.reply_text(f"❌ এরর হয়েছে:\n`{str(e)}`")

    finally:
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

print("🚀 মাল্টি-ক্যারেক্টার ডাবিং বট চালু হয়েছে...")
app.run()
