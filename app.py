import os
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIÓN DEL SISTEMA DE LOGGING
# ==========================================
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Iniciando aplicación de Asistente de Stock...')

# ==========================================
# 2. CONFIGURACIÓN DE GOOGLE SHEETS
# ==========================================
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ_bXNhxKs2BYMhNfwD1oNxm6Ao3rUI-BQeNqVUBLNKXBMDfEezr9L5KRtJfnYOpYnvGa6HbP99g-r4/pub?output=csv"

def obtener_datos_stock():
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        # Limpiar espacios en los nombres de las columnas por seguridad
        df.columns = df.columns.str.strip()
        app.logger.info("Datos de Google Sheets cargados exitosamente.")
        return df
    except Exception as e:
        app.logger.error(f"Error al conectar con Google Sheets: {str(e)}")
        return None

# ==========================================
# 3. INTERFAZ WEB (HTML / CSS / JS)
# ==========================================
HTML_CHAT = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Asistente de Stock</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .chat-container { width: 400px; background: white; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
        .chat-header { background: #343a40; color: white; padding: 15px; text-align: center; font-weight: bold; }
        .chat-box { height: 400px; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; border-bottom: 1px solid #ddd; }
        .message { padding: 10px 14px; border-radius: 6px; max-width: 80%; line-height: 1.4; }
        .message.bot { background: #e9ecef; align-self: flex-start; color: #333; }
        .message.user { background: #d4edda; align-self: flex-end; color: #155724; }
        .chat-input { display: flex; padding: 10px; background: #fff; }
        .chat-input input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; outline: none; }
        .chat-input button { background: #28a745; color: white; border: none; padding: 10px 15px; margin-left: 8px; border-radius: 4px; cursor: pointer; }
        .chat-input button:hover { background: #218838; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">Asistente de Stock</div>
        <div class="chat-box" id="chatBox">
            <div class="message bot">¡Hola! 😊 ¿Qué producto deseas consultar hoy o prefieres ver el catálogo completo?</div>
        </div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Escribe un mensaje..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">Enviar</button>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const userInput = document.getElementById('userInput');

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }

        async function sendMessage() {
            const text = userInput.value.trim();
            if (!text) return;

            chatBox.innerHTML += `<div class="message user">${text}</div>`;
            userInput.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/webhook', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                chatBox.innerHTML += `<div class="message bot">${data.message}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (error) {
                chatBox.innerHTML += `<div class="message bot">Error de conexión con el servidor.</div>`;
            }
        }
    </script>
</body>
</html>
"""

# ==========================================
# 4. RUTAS DE LA APLICACIÓN
# ==========================================
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_CHAT)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    user_message = ""

    if data and "message" in data:
        user_message = data.get("message", "").strip().lower()
    else:
        user_message = request.values.get("Body", "").strip().lower()

    app.logger.info(f"Mensaje recibido del usuario: {user_message}")

    # Lista de saludos
    saludos = ['hola', 'buendia', 'buen dia', 'buenas', 'hi', 'hello']

    if user_message in saludos:
        response_text = "¡Hola! 😊 ¿Qué producto deseas consultar hoy o prefieres ver el catálogo completo?"
        return jsonify({"message": response_text})

    df = obtener_datos_stock()
    
    if df is None or df.empty:
        return jsonify({"message": "Ocurrió un error al conectar con Google Sheets. Por favor, verifica el enlace o intenta más tarde."})

    response_text = ""

    # Asumimos las columnas por su posición segura (0: Producto, 1: Precio, 2: Cantidad)
    col_producto = df.columns[0]
    col_precio = df.columns[1]
    col_cantidad = df.columns[2]

    if "cat" in user_message or "catalogo" in user_message or "catálogo" in user_message:
        try:
            productos_lista = []
            for index, row in df.iterrows():
                nombre = str(row[col_producto]).strip().capitalize()
                cantidad = row[col_cantidad]
                precio = row[col_precio]
                productos_lista.append(f"• {nombre} - Cantidad: {cantidad} - Precio: ${precio}")
            response_text = "<b>Catálogo disponible:</b><br>" + "<br>".join(productos_lista)
        except Exception as e:
            app.logger.error(f"Error procesando el formato del catálogo: {str(e)}")
            response_text = "Hubo un problema al leer las columnas de la planilla."
    else:
        # Búsqueda parcial flexible (funciona con "pla", "emp", etc.)
        match = df[df[col_producto].astype(str).str.lower().str.contains(user_message, na=False)]
        if not match.empty:
            resultados = []
            for index, row in match.iterrows():
                nombre = str(row[col_producto]).strip().capitalize()
                cantidad = row[col_cantidad]
                precio = row[col_precio]
                resultados.append(f"<b>{nombre}</b>: Cantidad: {cantidad} | Precio: ${precio}")
            response_text = "<br>".join(resultados)
        else:
            response_text = f"No encontré productos que coincidan con '{user_message}'. Escribe 'cat' para ver el catálogo completo."

    return jsonify({"message": response_text})

if __name__ == "__main__":
    app.run(debug=True) 
