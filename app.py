import streamlit as st
import assemblyai as aai
import time
import threading
import queue

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

# Callback functions for the transcriber
def on_open(session_opened):
    st.session_state.session_id = session_opened.session_id
    st.session_state.transcription_queue.put(("info", f"Session opened with ID: {session_opened.session_id}"))

def on_data(transcript):
    if not transcript.text:
        return
    
    if isinstance(transcript, aai.RealtimeFinalTranscript):
        st.session_state.transcription_queue.put(("final", transcript.text))
        st.session_state.final_transcript.append(transcript.text)
    else:
        st.session_state.transcription_queue.put(("partial", transcript.text))

def on_error(error):
    st.session_state.transcription_queue.put(("error", f"Error: {error}"))

def on_close():
    st.session_state.transcription_queue.put(("info", "Session closed"))
    st.session_state.is_transcribing = False

# Function to start transcription in a separate thread
def start_transcription():
    try:
        # Configure the API key
        aai.settings.api_key = api_key
        
        # Create a transcriber
        transcriber = aai.RealtimeTranscriber(
            sample_rate=16_000,
            on_data=on_data,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close,
        )
        
        # Connect to the API
        transcriber.connect()
        
        # Start microphone stream
        microphone_stream = aai.extras.MicrophoneStream(sample_rate=16_000)
        
        # Stream audio until the stop button is pressed
        st.session_state.is_transcribing = True
        while st.session_state.is_transcribing:
            transcriber.stream(microphone_stream, auto_reconnect=True)
            time.sleep(0.1)
        
        # Close the connection
        transcriber.close()
        
    except Exception as e:
        st.session_state.transcription_queue.put(("error", f"Error: {str(e)}"))
        st.session_state.is_transcribing = False

# UI for controlling transcription
col1, col2 = st.columns(2)

with col1:
    start_button = st.button("Start Transcription", disabled=not api_key or st.session_state.is_transcribing)

with col2:
    stop_button = st.button("Stop Transcription", disabled=not st.session_state.is_transcribing)

if start_button and not st.session_state.is_transcribing and api_key:
    # Start transcription in a separate thread
    threading.Thread(target=start_transcription, daemon=True).start()

if stop_button and st.session_state.is_transcribing:
    st.session_state.is_transcribing = False

# Display area for real-time transcription
st.subheader("Real-time Transcription")
partial_placeholder = st.empty()
transcription_container = st.container()

# Display area for final transcripts
st.subheader("Completed Transcriptions")
final_transcript_container = st.container()

with final_transcript_container:
    for text in st.session_state.final_transcript:
        st.write(text)

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
                    with transcription_container:
                        st.success(message)
                elif msg_type == "error":
                    with transcription_container:
                        st.error(message)
                elif msg_type == "info":
                    with transcription_container:
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
       pip install streamlit "assemblyai[extras]"
       ```
       
    3. Run the app:
       ```
       streamlit run app.py
       ```
       
    4. Enter your AssemblyAI API key and start transcribing!
    """)

# Footer
st.caption("Note: AssemblyAI's streaming speech-to-text is only available for English.")
