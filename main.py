import os
import requests
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"

# Глобальная переменная для модели
ACTIVE_MODEL = None

# Словарь для хранения истории диалогов (память)
# Формат: { session_id: [ {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."} ] }
sessions = {}

# Максимальное количество сообщений в истории (чтобы не превысить лимит токенов)
MAX_HISTORY = 10

# Время жизни сессии в секундах (30 минут)
SESSION_LIFETIME = 1800


def get_best_available_model():
    """Автоматически выбирает лучшую доступную модель"""
    global ACTIVE_MODEL
    if ACTIVE_MODEL:
        return ACTIVE_MODEL

    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        response = requests.get(MODELS_URL, headers=headers)
        response.raise_for_status()
        models_data = response.json().get("data", [])
        model_ids = [m["id"] for m in models_data]

        priorities = ["llama-3", "qwen", "gemma", "mixtral"]
        for priority in priorities:
            for model_id in model_ids:
                if priority in model_id.lower():
                    ACTIVE_MODEL = model_id
                    print(f"✅ Авто-выбор: {ACTIVE_MODEL}")
                    return ACTIVE_MODEL

        if model_ids:
            ACTIVE_MODEL = model_ids[0]
            return ACTIVE_MODEL
    except Exception as e:        print(f"Ошибка при получении списка моделей: {e}")

    ACTIVE_MODEL = "llama3-8b-8192"
    return ACTIVE_MODEL


def cleanup_old_sessions():
    """Удаляет старые сессии, чтобы не забивать память сервера"""
    current_time = time.time()
    expired_keys = [k for k, v in sessions.items() 
                    if current_time - v.get('last_activity', 0) > SESSION_LIFETIME]
    for key in expired_keys:
        del sessions[key]


def get_session_history(session_id):
    """Получает историю сообщений для сессии"""
    cleanup_old_sessions()
    
    if session_id not in sessions:
        sessions[session_id] = {'messages': [], 'last_activity': time.time()}
    
    sessions[session_id]['last_activity'] = time.time()
    return sessions[session_id]['messages']


def add_to_history(session_id, role, content):
    """Добавляет сообщение в историю сессии"""
    if session_id not in sessions:
        sessions[session_id] = {'messages': [], 'last_activity': time.time()}
    
    sessions[session_id]['messages'].append({
        "role": role,
        "content": content
    })
    sessions[session_id]['last_activity'] = time.time()
    
    # Обрезаем историю, если она слишком длинная
    if len(sessions[session_id]['messages']) > MAX_HISTORY * 2:
        sessions[session_id]['messages'] = sessions[session_id]['messages'][-MAX_HISTORY * 2:]


def clear_session(session_id):
    """Очищает историю сессии"""
    if session_id in sessions:
        del sessions[session_id]


@app.route('/webhook', methods=['POST'])
def webhook():    data = request.json
    user_request = data.get('request', {}).get('original_utterance', 'Привет!').strip()
    
    # Получаем ID сессии от Яндекса (уникален для каждого диалога)
    session_id = data.get('session', {}).get('session_id', 'default')
    
    # Проверяем команду "забудь всё"
    if user_request.lower() in ['забудь всё', 'забудь все', 'начни сначала', 'очисти память', 'новая тема']:
        clear_session(session_id)
        ai_text = "Хорошо, я всё забыл. Давай начнём сначала! 😊"
    else:
        # Получаем текущую модель
        current_model = get_best_available_model()
        
        # Получаем историю диалога
        history = get_session_history(session_id)
        
        # Добавляем сообщение пользователя в историю
        add_to_history(session_id, "user", user_request)
        
        # Формируем список сообщений для Groq (системный промпт + история)
        messages = [
            {"role": "system", "content": "Ты полезный и дружелюбный ассистент по имени Квен. Отвечай кратко, по делу и на русском языке. Ты помнишь весь контекст текущего разговора."}
        ]
        
        # Добавляем последние MAX_HISTORY сообщений из истории
        messages.extend(history[-MAX_HISTORY * 2:])
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": current_model,
            "messages": messages,
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
                
        except Exception as e:            ai_text = f"Извините, произошла ошибка связи: {str(e)}"
        
        # Добавляем ответ ассистента в историю
        add_to_history(session_id, "assistant", ai_text)

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
