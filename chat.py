# chat.py — محادثة بسيطة بالترمينل مع نموذج LLM7B خاص عبر Hugging Face + ctransformers
from dotenv import load_dotenv
import os
from huggingface_hub import hf_hub_download
from ctransformers import AutoModelForCausalLM

# تحميل التوكن من ملف .env
load_dotenv()
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")

# إعدادات النموذج
MODEL_REPO = "TheBloke/Llama-2-7B-chat-GGML"  # استبدليها إذا عندك ريبوزيتوري آخر
MODEL_FILE = "llama-2-7b-chat.ggmlv3.q4_K_M.bin"  # اسم الملف داخل الريبوزيتوري (تقدرين تتأكدين منه في الصفحة)
CONFIG = {
    "model_type": "llama",
    "max_new_tokens": 128,
    "temperature": 0.8,
    "repetition_penalty": 1.1,
    "stream": False,
    "gpu_layers": 0
}

print("⏳ Downloading model from Hugging Face (with token)...")

# نحمل الملف أول مرة بالتوكن ونخزنه محلياً
model_path = hf_hub_download(
    repo_id=MODEL_REPO,
    filename=MODEL_FILE,
    token=HF_TOKEN
)

print("✅ Download complete. Loading model...")

# نحمل النموذج من المسار المحلي
llm = AutoModelForCausalLM.from_pretrained(model_path, **CONFIG)

print("✅ Model loaded successfully!\n🤖 Terminal Chat — اكتب exit للخروج.\n")

# حلقة المحادثة
history = []
while True:
    user = input("You: ").strip()
    if not user:
        continue
    if user.lower() in {"exit", "quit"}:
        print("Bye!")
        break

    prompt = (
        "You are a helpful assistant. Keep answers short and clear.\n\n"
        + "\n".join(history[-4:])
        + f"\nUser: {user}\nAssistant:"
    )
    reply = llm(prompt, stream=False)
    print(f"Assistant: {reply}\n")

    history += [f"User: {user}", f"Assistant: {reply}"]
