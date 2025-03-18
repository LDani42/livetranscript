import streamlit as st
import requests
import json
import time
import base64
from streamlit.components.v1 import html

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
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = None

# Function to handle audio data from frontend
def handle_audio_data():
    if st.session_state.audio_data and st.session_state.audio_data != "":
        process_audio(st.session_state.audio_data)
        
# Function to process audio data
def process_audio(audio_base64):
    with st.spinner("Processing audio..."):
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_base64)
            
            # Upload audio to AssemblyAI
            upload_url = upload_audio(audio_bytes)
            
            if upload_url:
                # Start transcription
                transcription_id = start_transcription(upload_url)
                if transcription_id:
                    st.session_state.transcription_id = transcription_id
                    st.experimental_rerun()
        except Exception as e:
            st.error(f"Error processing audio: {str(e)}")

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

# Use Streamlit's component HTML for the audio recorder
def recorder_component():
    component_value = st.session_state.get("audio_data", "")
    
    # JavaScript for audio recording
    recorder_html = """
    <script>
    // Counter to make key handling stable
    let recordingCounter = 0;
    
    // Function to start recording after component loads
    function setupRecorder() {
        const recordButton = document.getElementById('recordButton');
        const statusElement = document.getElementById('status');
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        let stream = null;
        
        // Make sure we can access the elements
        if (!recordButton || !statusElement) {
            console.error("Couldn't find required elements");
            return;
        }
        
        // Make the button actually clickable
        recordButton.addEventListener('click', async () => {
            try {
                if (!isRecording) {
                    // Start recording
                    statusElement.textContent = "Requesting microphone access...";
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];
                    
                    mediaRecorder.addEventListener('dataavailable', event => {
                        audioChunks.push(event.data);
                    });
                    
                    mediaRecorder.addEventListener('stop', () => {
                        statusElement.textContent = "Processing audio...";
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const reader = new FileReader();
                        reader.readAsDataURL(audioBlob);
                        reader.onloadend = () => {
                            const base64data = reader.result.split(',')[1];
                            // Send back to Streamlit
                            const key = `recorder_${recordingCounter++}`;
                            window.parent.postMessage({
                                type: "streamlit:setComponentValue",
                                value: base64data
                            }, "*");
                        };
                    });
                    
                    mediaRecorder.start();
                    isRecording = true;
                    recordButton.textContent = "Stop Recording";
                    recordButton.style.backgroundColor = "#ff5e5e";
                    statusElement.textContent = "Recording... Speak now";
                } else {
                    // Stop recording
                    mediaRecorder.stop();
                    isRecording = false;
                    recordButton.textContent = "Start Recording";
                    recordButton.style.backgroundColor = "#4CAF50";
                    statusElement.textContent = "Recording stopped, processing...";
                    
                    // Stop all tracks
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }
                }
            } catch (err) {
                statusElement.textContent = "Error: " + err.message;
                console.error("Recording error:", err);
            }
        });
    }
    
    // Setup when the document is loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupRecorder);
    } else {
        setupRecorder();
    }
    </script>
    
    <div style="display: flex; flex-direction: column; align-items: center; padding: 20px;">
        <button id="recordButton" style="padding: 12px 24px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; margin-bottom: 15px;">
            Start Recording
        </button>
        <p id="status" style="margin-top: 10px; font-style: italic;">Click the button to start recording</p>
    </div>
    """
    
    # Use the HTML component with a key for proper re-rendering
    audio_data = html(recorder_html, height=200, key="recorder")
    
    # Return the received data if available
    return audio_data

# Display the recorder
audio_data = recorder_component()

# Hidden widget to capture audio data
audio_receiver = st.text_input("Audio Data", key="audio_data", label_visibility="collapsed")

# Process audio data if received
if st.session_state.audio_data and st.session_state.audio_data != "":
    # Check if we've already processed this audio
    if "last_processed_audio" not in st.session_state or st.session_state.last_processed_audio != st.session_state.audio_data:
        st.session_state.last_processed_audio = st.session_state.audio_data
        process_audio(st.session_state.audio_data)

# Check status of ongoing transcription
if st.session_state.transcription_id:
    status_placeholder = st.empty()
    
    with status_placeholder.container():
        st.write("Transcribing audio...")
        progress_bar = st.progress(0)
        
        # Poll for results
        complete = False
        start_time = time.time()
        while not complete and time.time() - start_time < 60:  # Timeout after 60 seconds
            result = check_transcription_status(st.session_state.transcription_id)
            
            if result:
                st.session_state.transcription_status = result["status"]
                
                if result["status"] == "completed":
                    st.session_state.transcription_result = result["text"]
                    st.session_state.transcription_id = None  # Reset for next transcription
                    complete = True
                    progress_bar.progress(100)
                elif result["status"] == "error":
                    st.error(f"Transcription error: {result.get('error', 'Unknown error')}")
                    st.session_state.transcription_id = None
                    complete = True
                elif result["status"] == "processing":
                    # Update progress (approximate)
                    progress = min(int((time.time() - start_time) / 60 * 100), 90)
                    progress_bar.progress(progress)
                    time.sleep(1)
                else:
                    # Just wait for queued or other statuses
                    time.sleep(1)
            else:
                time.sleep(1)
        
        # Handle timeout
        if not complete:
            st.warning("Transcription is taking longer than expected. Please check results later or try again.")
            st.session_state.transcription_id = None
    
    # Rerun to update the UI after transcription is complete
    if complete:
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
        st.session_state.audio_data = None
        st.session_state.last_processed_audio = None
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
