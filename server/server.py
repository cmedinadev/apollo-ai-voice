import asyncio
import websockets
import numpy as np
from scipy.io.wavfile import write
from piper_tts import PiperTTSAdvanced
import openai
import whisper
import logging
import pvporcupine

# ===================== CONFIGURATION =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Apollo")

openai.api_key = "sk-proj-9sQKxxxx"

# Constants
CHUNK_SIZE = 1024
SAMPLE_RATE = 16000
MAX_HISTORY = 6
INPUT_AUDIO_FILE = "input.wav"
OUTPUT_AUDIO_FILE = "output.wav"

# Global state
connected_clients = set()
conversation_history = []
is_processing = False
wake_word_detected = False

# Wake word configuration
ACCESS_KEY = "88cCxxxxxx=="
WAKEWORD_PATH = "porcupine/apollo_wakeword.ppn"
MODEL_PATH = "porcupine/porcupine_params_pt.pv"

# ===================== MODEL INITIALIZATION =====================

def initialize_models():
    """Load all required models (Whisper, TTS, and Porcupine)."""
    logger.info("🧠 Loading models...")
    
    whisper_model = whisper.load_model("small")
    tts = PiperTTSAdvanced()
    porcupine = pvporcupine.create(
        access_key=ACCESS_KEY,
        keyword_paths=[WAKEWORD_PATH],
        model_path=MODEL_PATH
    )
    
    return whisper_model, tts, porcupine

# Initialize models globally
whisper_model, tts, porcupine = initialize_models()

# ===================== AUDIO HANDLING =====================

async def send_audio_chunks(websocket, filename):
    """Send audio file in chunks to ESP32."""
    try:
        with open(filename, "rb") as f:
            data = f.read()
        
        logger.info(f"📤 Sending {len(data)} bytes of audio...")
        
        for i in range(0, len(data), CHUNK_SIZE):
            chunk = data[i:i + CHUNK_SIZE]
            await websocket.send(chunk)
            await asyncio.sleep(0.024)
        
        logger.info("✅ Audio sent successfully.")
        await asyncio.sleep(0.5)
        
    except Exception as e:
        logger.error(f"🚫 Failed to send audio: {e}")

def save_audio_buffer(audio_buffer, filename):
    """Save audio buffer to WAV file."""
    audio_array = np.frombuffer(audio_buffer, dtype=np.int16)
    write(filename, SAMPLE_RATE, audio_array)
    logger.info(f"💾 Audio saved ({len(audio_buffer)} bytes)")

# ===================== SPEECH PROCESSING =====================

async def transcribe_audio(audio_file):
    """Convert audio to text using Whisper."""
    logger.info("🧠 Converting speech to text...")
    result = await asyncio.to_thread(
        whisper_model.transcribe, audio_file, fp16=False, language="pt"
    )
    return result["text"].strip()

def build_chat_messages():
    """Build the message list to send to ChatGPT."""
    system_message = {
        "role": "system",
        "content": (
            "Você é Apollo, um astronauta inteligente e sua missão é conversar e brincar com crianças.\n"
            "Responda com frases curtas, de forma alegre e carinhosa.\n"
            "Evite temas adultos, palavrões ou assuntos sérios.\n"
            "Conte histórias, curiosidades e piadas engraçadas.\n"
            "Sugira brincadeiras de advinhas e outras.\n"
            "Nunca responda com emojis.\n"
        ),
    }
    return [system_message] + conversation_history

def update_conversation_history(role, content):
    """Add message to history and maintain size limit."""
    conversation_history.append({"role": role, "content": content})
    
    if len(conversation_history) > MAX_HISTORY:
        conversation_history[:] = conversation_history[-MAX_HISTORY:]

async def get_chatgpt_response(user_text):
    """Get response from ChatGPT based on user text."""
    update_conversation_history("user", user_text)
    
    messages = build_chat_messages()
    response = openai.chat.completions.create(model="gpt-4.1-nano", messages=messages)
    response_text = response.choices[0].message.content
    
    update_conversation_history("assistant", response_text)
    logger.info(f"💬 Apollo: {response_text}")
    
    return response_text

async def synthesize_speech(text, output_file):
    """Synthesize text to audio using TTS."""
    await asyncio.to_thread(
        tts.synthesize_with_pitch, text, output_file, 2, 1.0, 0.667, 0.8
    )

async def process_audio_pipeline(websocket, audio_file):
    """Complete pipeline: STT → ChatGPT → TTS."""
    global is_processing
    
    try:
        # Transcription
        text = await transcribe_audio(audio_file)
        
        if not text:
            logger.warning("⚠️ No speech detected.")
            await websocket.send("interaction_ended")
            is_processing = False
            return None
        
        logger.info(f"🗣️ You said: {text}")
        
        # Get response
        response_text = await get_chatgpt_response(text)
        
        # Synthesize audio
        await synthesize_speech(response_text, OUTPUT_AUDIO_FILE)
        
        return response_text
        
    except Exception as e:
        logger.error(f"⚠️ Error processing audio: {e}")
        is_processing = False
        return None

# ===================== WAKE WORD DETECTION =====================

def detect_wake_word(buffer):
    """Process buffer and detect wake word."""
    frame_length_bytes = porcupine.frame_length * 2  # 16-bit audio
    temp_buffer = buffer[:]
    
    while len(temp_buffer) >= frame_length_bytes:
        frame = np.frombuffer(temp_buffer[:frame_length_bytes], dtype=np.int16)
        temp_buffer = temp_buffer[frame_length_bytes:]
        
        result = porcupine.process(frame)
        if result >= 0:
            logger.info("🚀 Wake word detected: 'Apolo'")
            return True
    
    return False

# ===================== MESSAGE HANDLERS =====================

async def handle_ping(websocket):
    """Respond to client ping."""
    await websocket.send("pong")

async def handle_wake_buffer_start(wake_buffer):
    """Start buffering wake word audio."""
    wake_buffer.clear()
    logger.info("🎙️ Starting wake word buffer...")

async def handle_wake_buffer_end(websocket, wake_buffer):
    """Process wake word buffer."""
    global wake_word_detected
    
    logger.info("🛑 Wake word buffer ended.")
    
    if wake_buffer:
        wake_word_detected = detect_wake_word(wake_buffer)
        
        if wake_word_detected:
            await websocket.send("wake_word_detected")
        else:
            logger.info("❌ Wake word not detected.")
            await websocket.send("wake_word_rejected")
        
        wake_buffer.clear()

async def handle_audio_start(audio_buffer):
    """Start buffering user audio."""
    audio_buffer.clear()
    logger.info("🎙️ Starting audio reception...")

async def handle_audio_end(websocket, audio_buffer):
    """Process user audio after recording ends."""
    global is_processing, wake_word_detected
    
    logger.info("🛑 Audio reception ended.")
    
    if not audio_buffer:
        return
    
    save_audio_buffer(audio_buffer, INPUT_AUDIO_FILE)
    
    if not is_processing:
        is_processing = True
        response_text = await process_audio_pipeline(websocket, INPUT_AUDIO_FILE)
        
        if response_text:
            await send_audio_chunks(websocket, OUTPUT_AUDIO_FILE)
        
        await asyncio.sleep(1)
        await websocket.send("interaction_ended")
        logger.info("✅ Interaction completed - ready for new wake word")
        is_processing = False
        wake_word_detected = False
    else:
        logger.info("⚠️ Already processing")

async def handle_text_message(websocket, message, wake_buffer, audio_buffer):
    """Process text messages received from client."""
    if message == "ping":
        await handle_ping(websocket)
        return False
    
    elif message == "wake_buffer_start":
        await handle_wake_buffer_start(wake_buffer)
        return True
    
    elif message == "wake_buffer_end":
        await handle_wake_buffer_end(websocket, wake_buffer)
        return False
    
    elif message == "start_audio":
        await handle_audio_start(audio_buffer)
        return None
    
    elif message == "end_audio":
        await handle_audio_end(websocket, audio_buffer)
        return None
    
    else:
        logger.info(f"📩 Text message: {message}")
        return None

def handle_binary_message(message, wake_buffer, audio_buffer, is_wake_buffering):
    """Process binary audio messages."""
    if is_wake_buffering:
        wake_buffer.extend(message)
    elif wake_word_detected:
        audio_buffer.extend(message)

# ===================== WEBSOCKET HANDLER =====================

async def websocket_handler(websocket):
    """Manage WebSocket connection and audio reception."""
    global is_processing, wake_word_detected
    
    connected_clients.add(websocket)
    logger.info("🤝 ESP32 connected!")

    audio_buffer = bytearray()
    wake_buffer = bytearray()
    is_wake_buffering = False

    try:
        async for message in websocket:
            # Handle text messages
            if isinstance(message, str):
                result = await handle_text_message(websocket, message, wake_buffer, audio_buffer)
                if result is not None:
                    is_wake_buffering = result
            
            # Handle binary audio data
            elif isinstance(message, (bytes, bytearray)):
                handle_binary_message(message, wake_buffer, audio_buffer, is_wake_buffering)

    except websockets.exceptions.ConnectionClosed:
        logger.info("📴 Connection closed by client")
    except Exception as e:
        logger.error(f"⚠️ Error in handler: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info("📴 ESP32 disconnected.")

# ===================== SERVER =====================

async def main():
    """Start WebSocket server."""
    server = await websockets.serve(
        websocket_handler, 
        "0.0.0.0", 
        8080, 
        ping_interval=20, 
        ping_timeout=60
    )
    logger.info("🚀 WebSocket server running on port 8080...")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

