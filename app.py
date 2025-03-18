import streamlit as st
import requests
import json
import time
import os
from io import BytesIO
import base64

# App title and description
st.title("Live Audio Transcription")
st.markdown("This app uses AssemblyAI to transcribe your speech. Record audio in your browser, then upload for transcription.")

# Initialize session state
if 'transcription_id' not in st.session_state:
    st.session_state.transcription_id = None
if 'transcription_status' not in st.session_state:
    st.session_state.transcription_status = None
if 'transcription_result' not in st.session_state:
    st.session_state.transcription_result = None

# Get API key from Streamlit secrets
api_key = st.secrets["assemblyai_api_key"]

# AssemblyAI API Endpoints
upload_endpoint = "https://api.assemblyai.com/v2/upload"
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"

# Set up headers for API requests
headers = {
    "Authorization": api_key,
    "Content-Type": "application/json"
}

# Function to upload audio to AssemblyAI
def upload_audio(audio_data):
    upload_headers = {
        "Authorization": api_key,
    }
    
    response = requests.post(
        upload_endpoint,
        headers=upload_headers,
        data=audio_data
    )
    
    if response.status_code == 200:
        return response.json()["upload_url"]
    else:
        st.error(f"Error uploading audio: {response.text}")
        return None

# Function to start transcription with AssemblyAI
def start_transcription(audio_url):
    data = {
        "audio_url": audio_url,
        "language_detection": True  # Automatically detect the language
    }
    
    response = requests.post(
        transcript_endpoint,
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        return response.json()["id"]
    else:
        st.error(f"Error starting transcription: {response.text}")
        return None

# Function to check transcription status
def check_transcription_status(transcription_id):
    polling_endpoint = f"{transcript_endpoint}/{transcription_id}"
    
    response = requests.get(polling_endpoint, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error checking transcription status: {response.text}")
        return None

# HTML/JS for browser-based audio recording
# This uses the browser's MediaRecorder API which is more reliable for cloud deployment
st.markdown("""
<style>
    .stButton button {
        width: 100%;
    }
    .record-button {
        background-color: #FF4B4B;
    }
    .stop-button {
        background-color: #4BD0FF;
    }
</style>

<script>
    const RECORDING_INSTRUCTIONS = document.getElementById('recording_instructions');
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    
    async function toggleRecording() {
        if (!isRecording) {
            // Start recording
            audioChunks = [];
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64data = reader.result.split(',')[1];
                    document.getElementById('audio_data').value = base64data;
                    document.getElementById('submit_audio').click();
                };
            };
            
            mediaRecorder.start();
            isRecording = true;
            document.getElementById('record_button').innerText = "Stop Recording";
            document.getElementById('record_button').className = "stop-button";
            document.getElementById('recording_status').innerText = "Recording... Speak now.";
        } else {
            // Stop recording
            mediaRecorder.stop();
            isRecording = false;
            document.getElementById('record_button').innerText = "Start Recording";
            document.getElementById('record_button').className = "record-button";
            document.getElementById('recording_status').innerText = "Processing audio...";
        }
    }
</script>

<div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;">
    <button id="record_button" class="record-button" onclick="toggleRecording()">Start Recording</button>
    <p id="recording_status"></p>
</div>

<input type="hidden" id="audio_data" name="audio_data">
""", unsafe_allow_html=True)

# Create hidden button to submit audio data
submit_audio = st.empty()
submit_placeholder = submit_audio.button("Submit Audio", key="submit_audio", style="display: none;")

# Handle audio submission
if st.session_state.get("audio_data"):
    with st.spinner("Processing audio..."):
        # Decode base64 audio data
        audio_bytes = base64.b64decode(st.session_state.audio_data)
        
        # Upload audio to AssemblyAI
        upload_url = upload_audio(audio_bytes)
        
        if upload_url:
            # Start transcription
            transcription_id = start_transcription(upload_url)
            if transcription_id:
                st.session_state.transcription_id = transcription_id
                st.experimental_rerun()

# Check status of ongoing transcription
if st.session_state.transcription_id:
    with st.spinner("Transcribing audio..."):
        result = check_transcription_status(st.session_state.transcription_id)
        
        if result:
            st.session_state.transcription_status = result["status"]
            
            if result["status"] == "completed":
                st.session_state.transcription_result = result["text"]
                st.session_state.transcription_id = None  # Reset for next transcription
                st.experimental_rerun()
            elif result["status"] == "error":
                st.error(f"Transcription error: {result['error']}")
                st.session_state.transcription_id = None
                st.experimental_rerun()
            else:
                time.sleep(1)
                st.experimental_rerun()

# Display transcription results
if st.session_state.transcription_result:
    st.markdown("### Transcription Result")
    st.write(st.session_state.transcription_result)
    
    # Download button for transcript
    st.download_button(
        label="Download Transcript",
        data=st.session_state.transcription_result,
        file_name="transcript.txt",
        mime="text/plain"
    )
    
    # Button to reset for a new recording
    if st.button("New Transcription"):
        st.session_state.transcription_result = None
        st.experimental_rerun()

# Instructions
with st.expander("Instructions", expanded=True):
    st.markdown("""
    1. Click **Start Recording** and grant microphone permissions when prompted
    2. Speak clearly into your microphone
    3. Click **Stop Recording** when you're finished
    4. Wait while your audio is transcribed
    5. View the transcription results and download if desired
    
    **Note:** This app uses the AssemblyAI API to process your speech. Transcription typically takes a few seconds.
    """)
