import streamlit as st
import assemblyai as aai
import tempfile
import os
import time
import threading
import queue

st.set_page_config(page_title="Audio Transcription", page_icon="🎤")

st.title("Audio Transcription App")
st.subheader("Powered by AssemblyAI")

# Create a text input for the API key
api_key = st.text_input("AssemblyAI API Key", type="password", 
                         help="You need an AssemblyAI API key to use this app. Visit https://www.assemblyai.com/ to get one.")

# Initialize session state variables
if 'transcription_queue' not in st.session_state:
    st.session_state.transcription_queue = queue.Queue()
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'final_transcript' not in st.session_state:
    st.session_state.final_transcript = []

# Function to transcribe audio
def transcribe_audio(audio_file):
    try:
        # Configure the API key
        aai.settings.api_key = api_key
        
        # Save the audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_file)
            temp_path = temp_audio.name
        
        st.session_state.is_processing = True
        st.session_state.transcription_queue.put(("info", "Processing audio..."))
        
        # Transcribe using AssemblyAI
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(temp_path)
        
        if transcript.text:
            st.session_state.transcription_queue.put(("final", transcript.text))
            st.session_state.final_transcript.append(transcript.text)
        else:
            st.session_state.transcription_queue.put(("error", "No speech detected in the audio."))
        
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass
            
    except Exception as e:
        st.session_state.transcription_queue.put(("error", f"Transcription error: {str(e)}"))
    finally:
        st.session_state.is_processing = False

# File upload for audio
st.subheader("Upload Audio File")
uploaded_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "m4a", "ogg"])

if uploaded_file is not None:
    # Display the uploaded audio
    st.audio(uploaded_file)
    
    # Add a button to transcribe the uploaded file
    if st.button("Transcribe Audio"):
        if api_key:
            threading.Thread(
                target=transcribe_audio, 
                args=(uploaded_file.getvalue(),), 
                daemon=True
            ).start()
        else:
            st.error("Please enter your AssemblyAI API key to transcribe audio.")

# Processing indicator
if st.session_state.is_processing:
    st.info("⏳ Processing audio... This may take a few moments.")

# Message area
message_container = st.container()

# Display area for transcriptions
st.subheader("Transcriptions")
transcription_container = st.container()

with transcription_container:
    for i, text in enumerate(st.session_state.final_transcript):
        st.markdown(f"**Transcription {i+1}:** {text}")

# Clear transcripts button
if st.session_state.final_transcript:
    if st.button("Clear All Transcripts"):
        st.session_state.final_transcript = []
        st.experimental_rerun()
    
    # Download button for all transcriptions
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
                
                if msg_type == "final":
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

# Instructions
with st.expander("How to Use"):
    st.markdown("""
    ## Instructions
    
    1. Enter your AssemblyAI API key in the field above.
    2. Upload an audio file (WAV, MP3, M4A, or OGG format).
    3. Click "Transcribe Audio" to process the file.
    4. Wait for the transcription to complete.
    5. View the transcription results below.
    6. You can download all transcriptions as a text file.
    
    ## Notes
    
    - This app uses AssemblyAI's transcription API.
    - Longer recordings may take more time to process.
    """)

# Footer
st.caption("Note: This app uses AssemblyAI's transcription API for audio files.")
