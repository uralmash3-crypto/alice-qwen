import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

HF_TOKEN = os.environ.get("HF_TOKEN")
MODEL_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-7B-Instruct"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    user_request = data.get('request', {}).get('original_utterance', 'Привет!')

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    prompt = f"<|im_start|>user\n{user_request}<|im_end|>\n<|im_start|>assistant\n"
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 256,
            "temperature": 0.7,
            "return_full_text": False
        }
    }
    
    try:
        response = requests.post(MODEL_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            ai_text = result[0].get('generated_text', 'Нет ответа').strip()
        elif "error" in result:
            ai_text = f"Модель просыпается: {result.get('error')}. Попробуйте через 30 секунд."
        else:
            ai_text = "Неожиданный формат ответа."
            
    except Exception as e:
        ai_text = f"Ошибка: {str(e)}"

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
