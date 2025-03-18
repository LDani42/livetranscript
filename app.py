import streamlit as st
import requests
import json
import time
import base64
import os

# App title and description
st.title("Live Audio Transcription")
st.markdown("This app uses AssemblyAI to transcribe your speech.")

# Initialize session state variables
if 'transcription_id' not in st.session_state:
    st.session_state.transcription_id = None
if 'transcription_result' not in st.session_state:
    st.session_state.transcription_result = None

# Get API key from Streamlit secrets
api_key = st.secrets.get("assemblyai_api_key", "")
if not api_key:
    st.error("Please set your AssemblyAI API key in the Streamlit secrets")

# AssemblyAI API Endpoints
upload_endpoint = "https://api.assemblyai.com/v2/upload"
transcript_endpoint = "https://api.assemblyai.com/v2/transcript"

# Headers for API requests
headers = {
    "Authorization": api_key,
    "Content-Type": "application/json"
}

# Function to upload audio to AssemblyAI
def upload_audio(audio_data):
    upload_headers = {
        "Authorization": api_key
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

# Function to start transcription
def start_transcription(audio_url):
    data = {
        "audio_url": audio_url,
        "language_detection": True
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

# Upload audio file option
st.subheader("Option 1: Upload an audio file")
uploaded_file = st.file_uploader("Choose an audio file", type=["mp3", "wav", "m4a"])

if uploaded_file and st.button("Transcribe Uploaded File"):
    with st.spinner("Processing audio file..."):
        # Get the audio data
        audio_bytes = uploaded_file.getvalue()
        
        # Upload to AssemblyAI
        upload_url = upload_audio(audio_bytes)
        
        if upload_url:
            # Start transcription
            transcription_id = start_transcription(upload_url)
            if transcription_id:
                st.session_state.transcription_id = transcription_id
                st.experimental_rerun()

# Audio recording option
st.subheader("Option 2: Record your voice")
st.markdown("""
⚠️ **Note:** The recording function works best in Chrome. You'll need to grant microphone permissions.
""")

# Create a JavaScript function to record audio
record_js = """
<script>
function recordAudio() {
    navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        const mediaRecorder = new MediaRecorder(stream);
        const audioChunks = [];
        
        // Start recording
        mediaRecorder.start();
        document.getElementById('rec_status').textContent = 'Recording... (speak now)';
        document.getElementById('start_button').style.display = 'none';
        document.getElementById('stop_button').style.display = 'inline-block';
        
        mediaRecorder.addEventListener('dataavailable', event => {
            audioChunks.push(event.data);
        });
        
        // On stop
        mediaRecorder.addEventListener('stop', () => {
            document.getElementById('rec_status').textContent = 'Recording stopped - processing...';
            
            // Convert audio to base64
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const reader = new FileReader();
            reader.readAsDataURL(audioBlob);
            reader.onloadend = () => {
                const base64Audio = reader.result.split(',')[1];
                document.getElementById('audio_data').value = base64Audio;
                document.getElementById('submit_audio').click();
            };
            
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
        });
        
        // Set up stop button
        document.getElementById('stop_button').addEventListener('click', () => {
            mediaRecorder.stop();
        });
    })
    .catch(err => {
        document.getElementById('rec_status').textContent = 'Error accessing microphone: ' + err.message;
    });
}
</script>

<div style="display: flex; flex-direction: column; align-items: center; padding: 10px;">
    <button id="start_button" onclick="recordAudio()" style="padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
        Start Recording
    </button>
    <button id="stop_button" style="display: none; padding: 10px 20px; background-color: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer;">
        Stop Recording
    </button>
    <p id="rec_status" style="margin-top: 10px; font-style: italic;"></p>
</div>
"""

# Display the recording interface
st.markdown(record_js, unsafe_allow_html=True)

# Hidden elements to receive data from JavaScript
audio_data = st.text_input("Audio Data", key="audio_data", label_visibility="collapsed")
submit_audio = st.button("Submit Audio", key="submit_audio", disabled=not audio_data)

# Process the recorded audio when submitted
if submit_audio and audio_data:
    try:
        # Decode the base64 audio
        audio_bytes = base64.b64decode(audio_data)
        
        with st.spinner("Processing recorded audio..."):
            # Upload to AssemblyAI
            upload_url = upload_audio(audio_bytes)
            
            if upload_url:
                # Start transcription
                transcription_id = start_transcription(upload_url)
                if transcription_id:
                    st.session_state.transcription_id = transcription_id
                    st.experimental_rerun()
    except Exception as e:
        st.error(f"Error processing audio: {str(e)}")

# Check transcription status
if st.session_state.transcription_id:
    status_placeholder = st.empty()
    
    with status_placeholder.container():
        st.write("Transcribing audio...")
        progress_bar = st.progress(0)
        
        # Poll for results
        complete = False
        start_time = time.time()
        
        while not complete and time.time() - start_time < 120:  # Timeout after 2 minutes
            result = check_transcription_status(st.session_state.transcription_id)
            
            if result:
                status = result.get("status")
                
                if status == "completed":
                    st.session_state.transcription_result = result.get("text", "")
                    st.session_state.transcription_id = None
                    complete = True
                    progress_bar.progress(100)
                elif status == "error":
                    st.error(f"Transcription error: {result.get('error', 'Unknown error')}")
                    st.session_state.transcription_id = None
                    complete = True
                else:
                    # Update progress (approximate)
                    progress = min(int((time.time() - start_time) / 120 * 100), 90)
                    progress_bar.progress(progress)
                    time.sleep(2)  # Check every 2 seconds
            else:
                time.sleep(2)
        
        # Handle timeout
        if not complete:
            st.warning("Transcription is taking longer than expected. Please check results later or try again.")
            st.session_state.transcription_id = None
    
    # Rerun to update the UI
    if complete:
        st.experimental_rerun()

# Display transcription results
if st.session_state.transcription_result:
    st.subheader("Transcription Result")
    st.write(st.session_state.transcription_result)
    
    # Download button
    st.download_button(
        label="Download Transcript",
        data=st.session_state.transcription_result,
        file_name="transcript.txt",
        mime="text/plain"
    )
    
    # New transcription button
    if st.button("New Transcription"):
        st.session_state.transcription_result = None
        st.experimental_rerun()

# Instructions
with st.expander("How to use this app"):
    st.markdown("""
    ### Option 1: Upload an audio file
    1. Click the "Browse files" button to upload an audio file
    2. Click "Transcribe Uploaded File" to start the transcription process
    
    ### Option 2: Record your voice
    1. Click "Start Recording" and grant microphone permissions when prompted
    2. Speak clearly into your microphone
    3. Click "Stop Recording" when finished
    
    ### What happens next
    - The app will upload your audio to AssemblyAI
    - You'll see a progress bar during transcription
    - When complete, you can view and download your transcript
    
    **Note:** This app uses the AssemblyAI API to process your speech. Transcription typically takes a few seconds to minutes depending on the length of your audio.
    """)
