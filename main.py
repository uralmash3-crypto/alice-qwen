import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

# Самая стабильная и доступная модель на Groq на данный момент
MODEL_NAME = "llama-3.3-70b-versatile" 

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    user_request = data.get('request', {}).get('original_utterance', 'Привет!')

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Ты полезный и дружелюбный ассистент по имени Джарвис. Отвечай кратко, по делу и на русском языке."},
            {"role": "user", "content": user_request}
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }
    
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers)
        
        if response.status_code != 200:
            # Если модель не найдена, попробуем запросить список доступных моделей для диагностики
            if response.status_code == 404:
                try:
                    models_resp = requests.get(MODELS_URL, headers=headers)
                    available_models = [m['id'] for m in models_resp.json().get('data', [])]
                    ai_text = f"Модель {MODEL_NAME} недоступна. Доступные модели: {', '.join(available_models[:5])}..."
                except:
                    ai_text = f"Ошибка API (код {response.status_code}): {response.text}"
            else:
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
