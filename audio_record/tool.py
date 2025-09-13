import pyaudio
import webrtcvad
import wave
from collections import deque
import datetime

# --- Configurații ---
FORMAT = pyaudio.paInt16  # Format audio (16-bit)
CHANNELS = 1             # Canale (mono)
RATE = 16000             # Rata de eșantionare (Hz). webrtcvad suportă 8000, 16000, 32000, 48000
FRAME_DURATION = 30      # Durata unui cadru audio în ms (10, 20 sau 30)
CHUNK_SIZE = int(RATE * FRAME_DURATION / 1000) # Numărul de eșantioane per cadru
VAD_AGGRESSIVENESS = 3   # Nivel de agresivitate VAD (0-3). 3 este cel mai agresiv în a detecta doar vocea.

SILENCE_SECONDS = 1      # Secunde de tăcere înainte de a salva fișierul
PRE_BUFFER_SIZE = 10     # Numărul de cadre audio de dinainte de detectarea vocii, pentru a nu tăia începutul cuvintelor.

DEVICE_INDEX = 1      # Indexul microfonului. Lasă 'None' pentru a folosi dispozitivul implicit.

# --- Inițializare ---
audio = pyaudio.PyAudio()
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

# --- Funcția de salvare a fișierului ---
def save_recording(frames, channels, sample_width, rate):
    """Salvează cadrele audio într-un fișier .wav cu un nume unic."""
    filename = f"inregistrare_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.wav"
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        
    print(f"✔ Înregistrare salvată ca: {filename}")

# --- Pornirea stream-ului audio ---
try:
    stream = audio.open(format=FORMAT,
                         channels=CHANNELS,
                         rate=RATE,
                         input=True,
                         input_device_index=DEVICE_INDEX,
                         frames_per_buffer=CHUNK_SIZE)

    print("🎤 Ascult microfonul... Aștept să detectez voce.")

    is_recording = False
    recorded_frames = []
    pre_buffer = deque(maxlen=PRE_BUFFER_SIZE)
    silent_chunks_count = 0
    
    # Numărul de bucăți de tăcere necesare pentru a declanșa salvarea
    SILENCE_CHUNKS_NEEDED = int(SILENCE_SECONDS * 1000 / FRAME_DURATION)

    # --- Bucla principală ---
    while True:
        try:
            audio_chunk = stream.read(CHUNK_SIZE)
            
            # Verifică dacă este voce în bucata audio
            is_speech = vad.is_speech(audio_chunk, RATE)

            if is_speech:
                if not is_recording:
                    # Am detectat voce, începem înregistrarea
                    print("🔴 Înregistrez...")
                    is_recording = True
                    # Adaugă bucățile de dinainte pentru a prinde începutul
                    recorded_frames.extend(list(pre_buffer))
                
                recorded_frames.append(audio_chunk)
                silent_chunks_count = 0
            else:
                # Nu este voce
                pre_buffer.append(audio_chunk) # Adaugă în pre-buffer
                
                if is_recording:
                    # Eram în proces de înregistrare, dar acum e tăcere
                    silent_chunks_count += 1
                    recorded_frames.append(audio_chunk) # Continuăm să adăugăm și bucățile de tăcere
                    
                    if silent_chunks_count > SILENCE_CHUNKS_NEEDED:
                        # S-a atins pragul de tăcere, salvăm
                        print("...tăcere detectată, salvez fișierul.")
                        save_recording(recorded_frames, CHANNELS, audio.get_sample_size(FORMAT), RATE)
                        
                        # Resetăm starea
                        is_recording = False
                        recorded_frames = []
                        pre_buffer.clear()
                        silent_chunks_count = 0
                        print("\n🎤 Ascult din nou...")

        except IOError as e:
            # Poate apărea dacă sunt prea multe date în buffer
            print(f"A apărut o eroare de I/O: {e}")

except KeyboardInterrupt:
    # Oprește scriptul cu Ctrl+C
    print("\n👋 Oprit de utilizator.")

finally:
    # --- Curățare ---
    if 'stream' in locals() and stream.is_active():
        stream.stop_stream()
        stream.close()
    audio.terminate()