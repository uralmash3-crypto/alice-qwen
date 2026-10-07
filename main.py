import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

ACTIVE_MODEL = None
memory = {}

def get_model():
    global ACTIVE_MODEL
    if ACTIVE_MODEL:
        return ACTIVE_MODEL
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        r = requests.get(MODELS_URL, headers=headers)
        models = [m["id"] for m in r.json().get("data", [])]
        for p in ["llama-3", "qwen", "gemma"]:
            for m in models:
                if p in m.lower():
                    ACTIVE_MODEL = m
                    return m
        if models:
            ACTIVE_MODEL = models[0]
            return ACTIVE_MODEL
    except:
        pass
    ACTIVE_MODEL = "llama3-8b-8192"
    return ACTIVE_MODEL

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    user_text = data.get('request', {}).get('original_utterance', 'Привет!').strip()
    session_id = data.get('session', {}).get('session_id', 'default')
    if user_text.lower() in ['забудь всё', 'забудь все', 'начни сначала', 'очисти память']:
        if session_id in memory:
            del memory[session_id]
        return jsonify({"version": "1.0", "session": data.get("session", {}), "response": {"text": "Хорошо, я всё забыл! Давай начнём сначала.", "end_session": False}})
    if session_id not in memory:
        memory[session_id] = []
    memory[session_id].append({"role": "user", "content": user_text})
    if len(memory[session_id]) > 10:
        memory[session_id] = memory[session_id][-10:]
    messages = [{"role": "system", "content": "Ты полезный ассистент по имени Квен. Отвечай кратко на русском языке. Ты помнишь контекст разговора."}]
    messages.extend(memory[session_id])
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": get_model(), "messages": messages, "temperature": 0.7, "max_tokens": 512}
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            ai_text = response.json()['choices'][0]['message']['content'].strip()
        else:
            ai_text = f"Ошибка API: {response.status_code}"
    except Exception as e:
        ai_text = f"Ошибка: {str(e)}"
    memory[session_id].append({"role": "assistant", "content": ai_text})
    return jsonify({"version": data.get("version", "1.0"), "session": data.get("session", {}), "response": {"text": ai_text, "end_session": False}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
