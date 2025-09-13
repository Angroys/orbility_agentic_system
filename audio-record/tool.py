import pyaudio
import webrtcvad
import wave
from collections import deque
import datetime
import os

class VoiceRecorder:
    """
    A class for a voice-activated recorder that listens for speech on a specified
    microphone (or automatically detects a DJI-connected one) and saves the audio
    to a WAV file when silence is detected.
    """

    def __init__(self, device_name_fragment="DJI", rate=16000, frame_duration=30, vad_aggressiveness=3):
        """
        Initializes the VoiceRecorder with audio configurations.

        Args:
            device_name_fragment (str): A fragment of the microphone's name to search for.
                                        Defaults to "DJI" to find a DJI-connected device.
            rate (int): The sample rate in Hz. Supported by webrtcvad: 8000, 16000, 32000, 48000.
            frame_duration (int): The duration of an audio frame in milliseconds (10, 20, or 30).
            vad_aggressiveness (int): The Voice Activity Detection (VAD) aggressiveness level (0-3).
                                      3 is the most aggressive in filtering out non-speech.
        """
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = rate
        self.FRAME_DURATION = frame_duration
        self.CHUNK_SIZE = int(self.RATE * self.FRAME_DURATION / 1000)
        self.VAD_AGGRESSIVENESS = vad_aggressiveness
        self.SILENCE_SECONDS = 1
        self.PRE_BUFFER_SIZE = 10
        self.SILENCE_CHUNKS_NEEDED = int(self.SILENCE_SECONDS * 1000 / self.FRAME_DURATION)
        self.DEVICE_NAME_FRAGMENT = device_name_fragment

        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(self.VAD_AGGRESSIVENESS)
        self.device_index = self._find_dji_microphone()

        if self.device_index is None:
            print("❗ Avertisment: Nu a fost detectat niciun microfon DJI. Se folosește dispozitivul implicit.")
            
    def _find_dji_microphone(self):
        """
        Searches for a microphone device whose name contains the specified fragment.

        Returns:
            int or None: The index of the first matching device, or None if not found.
        """
        print(f"🔍 Caut microfon cu numele '{self.DEVICE_NAME_FRAGMENT}'...")
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if self.DEVICE_NAME_FRAGMENT.lower() in device_info['name'].lower() and device_info['maxInputChannels'] > 0:
                print(f"✔ Microfon DJI '{device_info['name']}' găsit la indexul {i}.")
                return i
        return None

    def _save_recording(self, frames):
        """
        Saves the recorded audio frames to a WAV file with a unique filename.

        Args:
            frames (list): A list of audio chunks (bytes).
        """
        output_dir = "inregistrari"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = os.path.join(output_dir, f"inregistrare_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.wav")

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))
        
        print(f"✔ Înregistrare salvată ca: {filename}")

    def start_recording(self):
        """
        Starts the main recording loop, listening for voice activity and saving files.
        """
        print("--- Voice Recorder activat ---")
        stream = None
        try:
            stream = self.audio.open(format=self.FORMAT,
                                     channels=self.CHANNELS,
                                     rate=self.RATE,
                                     input=True,
                                     input_device_index=self.device_index,
                                     frames_per_buffer=self.CHUNK_SIZE)

            print("🎤 Ascult microfonul... Aștept să detectez voce.")

            is_recording = False
            recorded_frames = []
            pre_buffer = deque(maxlen=self.PRE_BUFFER_SIZE)
            silent_chunks_count = 0

            while True:
                try:
                    audio_chunk = stream.read(self.CHUNK_SIZE)
                    is_speech = self.vad.is_speech(audio_chunk, self.RATE)

                    if is_speech:
                        if not is_recording:
                            print("🔴 Înregistrez...")
                            is_recording = True
                            recorded_frames.extend(list(pre_buffer))
                        
                        recorded_frames.append(audio_chunk)
                        silent_chunks_count = 0
                    else:
                        pre_buffer.append(audio_chunk)
                        
                        if is_recording:
                            silent_chunks_count += 1
                            recorded_frames.append(audio_chunk)
                            
                            if silent_chunks_count > self.SILENCE_CHUNKS_NEEDED:
                                print("...tăcere detectată, salvez fișierul.")
                                self._save_recording(recorded_frames)
                                
                                is_recording = False
                                recorded_frames = []
                                pre_buffer.clear()
                                silent_chunks_count = 0
                                print("\n🎤 Ascult din nou...")

                except IOError as e:
                    print(f"A apărut o eroare de I/O: {e}")
                    # Poate fi necesară o logică de recuperare aici

        except KeyboardInterrupt:
            print("\n👋 Oprit de utilizator.")

        finally:
            if stream and stream.is_active():
                stream.stop_stream()
                stream.close()
            self.audio.terminate()

if __name__ == "__main__":
    # Crează o instanță a clasei și pornește înregistrarea
    recorder = VoiceRecorder(device_name_fragment="DJI")
    recorder.start_recording()