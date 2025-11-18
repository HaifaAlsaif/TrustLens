from firebase_realtime_setup import rtdb_root
from datetime import datetime, timezone

from dotenv import load_dotenv
import os
from huggingface_hub import hf_hub_download
from ctransformers import AutoModelForCausalLM


# ---------------------------
# تحميل التوكن
# ---------------------------
load_dotenv()
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")


# ---------------------------
# إعدادات النموذج
# ---------------------------
MODEL_REPO = "TheBloke/Llama-2-7B-chat-GGML"
MODEL_FILE = "llama-2-7b-chat.ggmlv3.q4_K_M.bin"
CONFIG = {
    "model_type": "llama",
    "max_new_tokens": 128,
    "temperature": 0.7,
    "repetition_penalty": 1.1,
    "stream": False,
    "gpu_layers": 0,
}

print("⏳ Downloading model from Hugging Face...")

model_path = hf_hub_download(
    repo_id=MODEL_REPO,
    filename=MODEL_FILE,
    token=HF_TOKEN,
)

print("✅ Model downloaded. Loading...")

llm = AutoModelForCausalLM.from_pretrained(model_path, **CONFIG)

print("✅ Model loaded!\n🤖 Terminal Chat — اكتب exit للخروج.\n")


# ---------------------------
# إنشاء Conversation جديد داخل generate_Conversation_llm
# ---------------------------
conv_ref = rtdb_root.child("generate_Conversation_llm").push({
    "startedAt": datetime.now(timezone.utc).isoformat(),
    "source": "terminal-chat",
})

messages_ref = conv_ref.child("messages")


# ---------------------------
# حفظ رسالة في Firebase
# ---------------------------
def save_message(sender: str, text: str):
    try:
        messages_ref.push({
            "sender": sender,
            "text": text,
            "time": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        print("[WARN] لم نستطع حفظ الرسالة في Firebase:", e)


# ---------------------------
# توليد رد من الموديل
# ---------------------------
def generate_reply(user_message: str) -> str:

    prompt = f"""
You are a concise and helpful AI assistant.
- Reply clearly.
- Do NOT roleplay.
- Do NOT generate stories.
- Keep responses short and helpful.

User: {user_message}
Assistant:
""".strip()

    raw = llm(prompt, max_new_tokens=128, temperature=0.7)
    text = str(raw)

    # تنظيف الرد
    text = text.replace("User:", "").replace("Assistant:", "").strip()

    return text


# ---------------------------
# حلقة المحادثة
# ---------------------------
while True:
    user = input("You: ").strip()
    if not user:
        continue

    if user.lower() in {"exit", "quit"}:
        print("Bye!")
        break

    save_message("user", user)

    bot_reply = generate_reply(user)
    print("Bot:", bot_reply)

    save_message("bot", bot_reply)
