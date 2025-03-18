import streamlit as st
import assemblyai as aai
import pyaudio
import wave
import tempfile
import threading
import queue
import os
import time
import io

st.set_page_config(page_title="Real-time Audio Transcription", page_icon="🎤")

st.title("Real-time Audio Transcription")
st.subheader("Powered by AssemblyAI")

# Create a text input for the API key
api_key = st.text_input("AssemblyAI API Key", type="password", 
                         help="You need an AssemblyAI API key to use this app. Visit https://www.assemblyai.com/ to get one.")

# Initialize session state variables
if 'transcription_queue' not in st.session_state:
    st.session_state.transcription_queue = queue.Queue()
if 'is_transcribing' not in st.session_state:
    st.session_state.is_transcribing = False
if 'final_transcript' not in st.session_state:
    st.session_state.final_transcript = []
if 'recording_path' not in st.session_state:
    st.session_state.recording_path = None

# Audio recorder class
class AudioRecorder:
    def __init__(self, sample_rate=16000, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        
    def start_recording(self):
        self.frames = []
        self.is_recording = True
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
    def record_chunk(self):
        if self.stream and self.is_recording:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            self.frames.append(data)
            return data
        return None
    
    def stop_recording(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.is_recording = False
        
    def save_recording(self, filename):
        if not self.frames:
            return False
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.frames))
        return True
    
    def __del__(self):
        if self.stream:
            self.stream.close()
        self.p.terminate()

# Function to record audio and save to file
def record_audio():
    try:
        # Create temporary file
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, "recording.wav")
        st.session_state.recording_path = file_path
        
        # Set up recorder
        recorder = AudioRecorder(sample_rate=16000)
        recorder.start_recording()
        
        st.session_state.transcription_queue.put(("info", "Started recording. Speak now..."))
        
        # Record until stop button is pressed
        st.session_state.is_transcribing = True
        recording_duration = 0
        chunk_duration = recorder.chunk_size / recorder.sample_rate
        
        while st.session_state.is_transcribing:
            recorder.record_chunk()
            recording_duration += chunk_duration
            
            # Every 5 seconds, save the current recording and transcribe
            if recording_duration >= 5:
                # Save temporary file
                temp_file = os.path.join(temp_dir, f"temp_{time.time()}.wav")
                recorder.save_recording(temp_file)
                
                # Transcribe
                try:
                    aai.settings.api_key = api_key
                    transcriber = aai.Transcriber()
                    transcript = transcriber.transcribe(temp_file)
                    
                    if transcript.text:
                        st.session_state.transcription_queue.put(("partial", transcript.text))
                except Exception as e:
                    st.session_state.transcription_queue.put(("error", f"Transcription error: {str(e)}"))
                
                # Clean up
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                recording_duration = 0
        
        # Final save
        if recorder.frames:
            recorder.save_recording(file_path)
            st.session_state.transcription_queue.put(("info", f"Recording saved to {file_path}"))
            
            # Final transcription
            try:
                aai.settings.api_key = api_key
                transcriber = aai.Transcriber()
                transcript = transcriber.transcribe(file_path)
                
                if transcript.text:
                    st.session_state.transcription_queue.put(("final", transcript.text))
                    st.session_state.final_transcript.append(transcript.text)
            except Exception as e:
                st.session_state.transcription_queue.put(("error", f"Final transcription error: {str(e)}"))
        
        # Clean up
        recorder.stop_recording()
        
    except Exception as e:
        st.session_state.transcription_queue.put(("error", f"Recording error: {str(e)}"))
    finally:
        st.session_state.is_transcribing = False

# UI for controlling transcription
col1, col2 = st.columns(2)

with col1:
    start_button = st.button("Start Recording", disabled=not api_key or st.session_state.is_transcribing, key="start_btn")

with col2:
    stop_button = st.button("Stop Recording", disabled=not st.session_state.is_transcribing, key="stop_btn")

# Add status indicator
status_container = st.empty()
if st.session_state.is_transcribing:
    status_container.markdown("🔴 **Recording in progress...**")
else:
    status_container.info("Click 'Start Recording' to begin capturing audio from your microphone.")

# Start/stop logic
if start_button and not st.session_state.is_transcribing and api_key:
    # Start recording in a separate thread
    threading.Thread(target=record_audio, daemon=True).start()

if stop_button and st.session_state.is_transcribing:
    st.session_state.is_transcribing = False
    status_container.warning("Stopping recording and processing final transcription...")

# Display area for real-time transcription
st.subheader("Current Transcription")
partial_placeholder = st.empty()

# Message area
message_container = st.container()

# Display area for final transcripts
st.subheader("Completed Transcriptions")
final_transcript_container = st.container()

with final_transcript_container:
    for i, text in enumerate(st.session_state.final_transcript):
        st.markdown(f"**Transcription {i+1}:** {text}")

# Add audio playback for the last recording
if st.session_state.recording_path and os.path.exists(st.session_state.recording_path):
    st.subheader("Last Recording")
    with open(st.session_state.recording_path, "rb") as f:
        audio_bytes = f.read()
    st.audio(audio_bytes, format="audio/wav")

# Clear transcripts button
if st.button("Clear All Transcripts"):
    st.session_state.final_transcript = []
    st.experimental_rerun()

# Download button for all transcriptions
if st.session_state.final_transcript:
    combined_text = "\n".join(st.session_state.final_transcript)
    st.download_button(
        label="Download Transcriptions",
        data=combined_text,
        file_name="transcription.txt",
        mime="text/plain"
    )

# Function to update the UI with transcription results
def update_ui():
    while True:
        try:
            if not st.session_state.transcription_queue.empty():
                msg_type, message = st.session_state.transcription_queue.get(block=False)
                
                if msg_type == "partial":
                    partial_placeholder.markdown(f"*{message}*")
                elif msg_type == "final":
                    partial_placeholder.empty()
                    with message_container:
                        st.success(message)
                elif msg_type == "error":
                    with message_container:
                        st.error(message)
                elif msg_type == "info":
                    with message_container:
                        st.info(message)
            
            time.sleep(0.1)
        except Exception:
            time.sleep(0.1)

# Start UI update in a separate thread
if 'ui_thread' not in st.session_state:
    st.session_state.ui_thread = threading.Thread(target=update_ui, daemon=True)
    st.session_state.ui_thread.start()

# Show installation instructions
with st.expander("Installation Instructions"):
    st.markdown("""
    ## Prerequisites
    1. Python installed on your system
    2. An AssemblyAI account with a credit card set up
    
    ## Setup Instructions
    1. Install PortAudio (required for microphone access):
       - **macOS**: `brew install portaudio`
       - **Windows**: PortAudio comes with the Python packages below
       - **Linux**: `sudo apt-get install portaudio19-dev`
       
    2. Install required Python packages:
       ```
       pip install streamlit assemblyai pyaudio
       ```
       
    3. Run the app:
       ```
       streamlit run app.py
       ```
       
    4. Enter your AssemblyAI API key and start transcribing!
    """)

# Footer
st.caption("Note: This app uses AssemblyAI's transcription API. Each recording is processed in batches.")
