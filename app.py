import streamlit as st
import assemblyai as aai
import threading
import time
import queue

# App title and description
st.title("Live Audio Transcription")
st.markdown("This app uses AssemblyAI to transcribe your speech in real-time.")

# Initialize session state variables if they don't exist
if 'transcript_queue' not in st.session_state:
    st.session_state.transcript_queue = queue.Queue()
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'final_transcript' not in st.session_state:
    st.session_state.final_transcript = []
if 'current_partial' not in st.session_state:
    st.session_state.current_partial = ""
if 'transcriber' not in st.session_state:
    st.session_state.transcriber = None
if 'transcriber_thread' not in st.session_state:
    st.session_state.transcriber_thread = None

# Get API key from Streamlit secrets
api_key = st.secrets["assemblyai_api_key"]

# Configure AssemblyAI with API key
aai.settings.api_key = api_key

# Callback functions for the real-time transcriber
def on_open(session_opened):
    st.session_state.transcript_queue.put(("info", f"Session opened with ID: {session_opened.session_id}"))

def on_data(transcript):
    if not transcript.text:
        return
    
    if isinstance(transcript, aai.RealtimeFinalTranscript):
        st.session_state.transcript_queue.put(("final", transcript.text))
    else:
        st.session_state.transcript_queue.put(("partial", transcript.text))

def on_error(error):
    st.session_state.transcript_queue.put(("error", f"Error: {error}"))

def on_close():
    st.session_state.transcript_queue.put(("info", "Session closed"))

# Function to start transcription
def start_transcription():
    # Create the transcriber
    transcriber = aai.RealtimeTranscriber(
        sample_rate=16000,
        on_data=on_data,
        on_error=on_error,
        on_open=on_open,
        on_close=on_close,
    )
    
    # Connect to AssemblyAI
    transcriber.connect()
    
    # Create a microphone stream
    microphone_stream = aai.extras.MicrophoneStream(sample_rate=16000)
    
    # Start streaming audio
    try:
        transcriber.stream(microphone_stream)
    except Exception as e:
        st.session_state.transcript_queue.put(("error", f"Streaming error: {e}"))
    finally:
        transcriber.close()
    
    return transcriber

# Function to run in a separate thread
def transcription_thread():
    transcriber = start_transcription()
    st.session_state.transcriber = transcriber
    
    while st.session_state.is_recording:
        time.sleep(0.1)
    
    # Clean up when stopping
    if transcriber:
        transcriber.close()

# UI for starting and stopping recording
col1, col2 = st.columns(2)

with col1:
    start_button = st.button("Start Recording", disabled=st.session_state.is_recording)

with col2:
    stop_button = st.button("Stop Recording", disabled=not st.session_state.is_recording)

# Handle button clicks
if start_button:
    st.session_state.is_recording = True
    st.session_state.final_transcript = []
    st.session_state.current_partial = ""
    
    # Start transcription in a separate thread
    transcriber_thread = threading.Thread(target=transcription_thread)
    transcriber_thread.daemon = True
    transcriber_thread.start()
    st.session_state.transcriber_thread = transcriber_thread
    
    st.experimental_rerun()

if stop_button:
    st.session_state.is_recording = False
    st.experimental_rerun()

# Display area for transcripts
st.markdown("### Live Transcription")

# Container for real-time transcription
live_container = st.empty()

# Container for final transcription
st.markdown("### Final Transcript")
final_container = st.empty()

# Function to update the transcript display
def update_transcript():
    # Combine all final transcript sentences
    final_text = " ".join(st.session_state.final_transcript)
    final_container.markdown(final_text)
    
    # Show the current partial transcript
    if st.session_state.current_partial:
        combined = f"{final_text} {st.session_state.current_partial}..."
    else:
        combined = final_text
    
    live_container.markdown(combined)

# Process any items in the queue
while not st.session_state.transcript_queue.empty():
    msg_type, content = st.session_state.transcript_queue.get()
    
    if msg_type == "final":
        st.session_state.final_transcript.append(content)
        st.session_state.current_partial = ""
    elif msg_type == "partial":
        st.session_state.current_partial = content
    elif msg_type == "error" or msg_type == "info":
        st.info(content)

# Update the display
update_transcript()

# Download button for the transcript
if st.session_state.final_transcript:
    transcript_text = " ".join(st.session_state.final_transcript)
    st.download_button(
        label="Download Transcript",
        data=transcript_text,
        file_name="transcript.txt",
        mime="text/plain"
    )

# Add a note about dependencies
st.markdown("""
---
**Note:** This app requires the following dependencies:
- `assemblyai[extras]`
- PortAudio (for microphone access)

Make sure to install them before running this app:
```
pip install "assemblyai[extras]" streamlit
```

For macOS: `brew install portaudio`
For Windows/Linux: Follow AssemblyAI's installation instructions
""")
