import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

# Глобальная переменная для сохранения выбранной модели (чтобы не запрашивать список каждый раз)
ACTIVE_MODEL = None

def get_best_available_model():
    global ACTIVE_MODEL
    if ACTIVE_MODEL:
        return ACTIVE_MODEL
        
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        response = requests.get(MODELS_URL, headers=headers)
        response.raise_for_status()
        models_data = response.json().get("data", [])
        
        # Извлекаем только ID моделей
        model_ids = [m["id"] for m in models_data]
        
        # Приоритетный список: ищем модели по ключевым словам (от лучших к простым)
        priorities = ["llama-3", "qwen", "gemma", "mixtral"]
        
        for priority in priorities:
            for model_id in model_ids:
                if priority in model_id.lower():
                    ACTIVE_MODEL = model_id
                    print(f"✅ Авто-выбор: найдена модель {ACTIVE_MODEL}")
                    return ACTIVE_MODEL
        
        # Если ни одна из приоритетных не найдена, берем самую первую доступную
        if model_ids:
            ACTIVE_MODEL = model_ids[0]
            print(f"⚠️ Приоритетные модели не найдены. Используем первую доступную: {ACTIVE_MODEL}")
            return ACTIVE_MODEL
            
    except Exception as e:
        print(f"Ошибка при получении списка моделей: {e}")
        
    # Самый крайний случай (фолбэк)
    ACTIVE_MODEL = "llama3-8b-8192"
    return ACTIVE_MODEL

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    user_request = data.get('request', {}).get('original_utterance', 'Привет!')

    # Получаем актуальную модель
    current_model = get_best_available_model()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": current_model,
        "messages": [
            {"role": "system", "content": "Ты полезный и дружелюбный ассистент по имени Qwen. Отвечай кратко, по делу и на русском языке."},
            {"role": "user", "content": user_request}
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }
    
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers)
        
        if response.status_code != 200:
            ai_text = f"Ошибка API (код {response.status_code}): {response.text}"
        else:
            result = response.json()
            ai_text = result['choices'][0]['message']['content'].strip()
            
    except Exception as e:
        ai_text = f"Извините, произошла ошибка связи: {str(e)}"

    return jsonify({
        "version": data.get("version", "1.0"),
        "session": data.get("session", {}),
        "response": {
            "text": ai_text,
            "end_session": False
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
