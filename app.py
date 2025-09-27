import streamlit as st
from gtts import gTTS
import io
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
import pickle
from pydub import AudioSegment
from faster_whisper import WhisperModel
import subprocess
import os
import pickle
import threading
import time


f = open('gemini_api.pkl', 'rb')
MY_API_KEY = pickle.load(f)
f.close()
genai.configure(api_key=MY_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
LEVEL = 2
REMAINING_QUESTIONS = 3
ft = open('topics.bin', 'rb')
topics = pickle.load(ft)
ft.close()
SCORE = []
f = open('exception_commands.bin', 'rb')
VULN_KEYS = pickle.load(f)
f.close()
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")


def security_check_ifsafe(code, lang):
    for key in VULN_KEYS[lang]:
        if key in code:
            return  False
    return True

def run_code(code):
    output = ""
    if security_check_ifsafe(code, 'python'):
        try:
            with open("temp_script.py", "w") as f:
                f.write(code)
            
            result = subprocess.run(
                ['.\\python\\python.exe', 'temp_script.py'],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout + result.stderr
        # if an error occurs then it produces the error in the frontend terminal
        except Exception as e:
            output = str(e)
        finally:
            # Deleting temp files
            if os.path.exists("temp_script.py"):
                os.remove("temp_script.py")
    else:
        output = "Access Denied"
            
    return output


def install_package(package_name: str):
    if not package_name or not package_name.isalnum():
        return -1
    # Running cmd commands
    try:
        result = subprocess.run(
            ['pip', 'install', package_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        log = result.stdout + result.stderr
        success = result.returncode == 0
        return log, True
    except Exception as e:
        return str(e), False

def run_cpp_code(code):
    output = ""
    if security_check_ifsafe(code, 'cpp'):
        cpp_filename = "temp_script.cpp"
        executable_filename = "temp_executable"
        try:
            # code in file with gcc extension
            with open(cpp_filename, "w") as f:
                f.write(code)
            compile_result = subprocess.run(
                ['g++.exe', cpp_filename, '-o', executable_filename],
                capture_output=True,
                text=True,
                timeout=10
            )
            if compile_result.returncode != 0:
                output = compile_result.stderr
            else:
                # if no error
                run_result = subprocess.run(
                    [f'./{executable_filename}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                output = run_result.stdout + run_result.stderr

        except Exception as e:
            output = str(e)
        finally:
            # Deleting compiled and base code after getting output
            if os.path.exists(cpp_filename):
                os.remove(cpp_filename)
            if os.path.exists(executable_filename):
                os.remove(executable_filename)
    else:
        output = "Access Denied"
    return output


def transcribe_audio():
    print("Transcribing audio...")
    try:
        segments, info = whisper_model.transcribe("temp_audio.wav", language="en", beam_size=5)
        transcript = ""
        for segment in segments:
            segment_text = segment.text.strip()
            transcript += segment_text + " "
        print(f"Transcription complete", "-",transcript.strip())
        return transcript.strip()
    except Exception as e:
        print(f"Audio transcription failed: {e}")

def convert_webm_to_wav(webm_bytes):
    """Converts audio from webm bytes to wav bytes."""
    try:
        segment = AudioSegment.from_file(io.BytesIO(webm_bytes), format="webm")
        wav_io = io.BytesIO()
        segment.export(wav_io, format="wav")
        return wav_io.getvalue()
    except Exception as e:
        print(f"Error converting audio: {e}")
        return None
    

def gemini_response(prompt_text):
    response = model.generate_content(prompt_text)
    return response.text 


st.set_page_config(
    page_title="Lanister - AI Interviewer",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Main chat container */
    .st-emotion-cache-1jicfl2 {
        padding-top: 2rem;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F0F2F6;
    }
    [data-testid="stSidebar"] h2 {
        color: #1E293B;
    }
    /* Chat messages */
    .stChatMessage {
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    }
    /* Tall text area for code */
    textarea[data-baseweb="textarea"] {
        height: 500px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def text_to_speech(text):
    try:
        audio_fp = io.BytesIO()
        tts = gTTS(text=text, lang='en', slow=False)
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        return audio_fp.read()
    except Exception as e:
        st.error(f"Could not generate audio: {e}")
        return None

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello, Today we will do a mock interview.\nPlease Choose your preferred language"}]
if "code_content" not in st.session_state:
    st.session_state.code_content = ""

st.title("Lanister - AI Interviewer")
chat_col, code_col = st.columns(2)


st.sidebar.header("Code Editor")
code_col = st.sidebar.text_area(
    "Editable Code Panel",
    value=st.session_state.code_content,
    height=750,
    width=700,
    label_visibility="collapsed"
)


def monitoring_bot():
    
    OLD = ""
    while True:
        final_prompt = f"""You are an AI Tech Interviewer, Based on history of responses
        You are called for checking the code written by user and you may intervene if user is going wrong way.
        And This is the Code Window with old code-
        '{OLD}'
        
        And This is the Code Window with changes
        '{st.session_state.code_content}'
        Based on the code changes and the history of responses, you may intervene if user is going wrong way or you may choose to wait for user to complete or if he is going wrong way then you may give him any hint
        History of responses: '{history}'
        
        For intervention strictly just return 0 followed by your response or hint else just return -1"""

        OLD = st.session_state.code_content
        
        response = gemini_response(final_prompt)
        if response[0] == '0':
            response = response[1:response.find("```")]
            st.session_state.messages.append({"role": "assistant", "content": response})
            history.append({"role": "assistant", "content": response})
            st.experimental_rerun()
        else:
            print("No intervention needed")
            # So changes will be suggested


        time.sleep(10)


        n += 1



with chat_col:
    st.header("Chat")
    # Display all history messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            # Read aloud button
            if message["role"] == "assistant":
                audio_bytes = text_to_speech(message["content"])
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

    st.markdown("---")
    st.markdown("#### Input by Speech")
    # audio_info = mic_recorder(
    #     start_prompt="Speak 🎙️",
    #     stop_prompt="Stop ⏹️",
    #     key='speech_input'
    # )

    audio = st.audio_input("Speak")      

    prompt = st.chat_input("Respond here...")

# if audio_info and audio_info['bytes']:
#     st.info("Speech received. You would now transcribe this audio.")
#     prompt = "This is a placeholder for the transcribed speech."
#     st.warning("Speech-to-text is a placeholder. To implement it, you need to connect to a transcription service.")

def phraser(user_response):
    text = f"""You are an AI Tech Interviewer and Based on the History of responses
    You have to ask the next question from the list of topics.
    
    Topics are - {topics}

    ask user LEVEL {LEVEL} question.
]
    You have to ask a total of 10 independent questions from the above list.
    if the user is not able to answer then you can go to one LEVEL less.
    If the user is able to answer then you can go to LEVEL 3 and so on
    
    And This is the Code Window -
    '{st.session_state.code_content}'
    Based on the code and the history of responses, ask the next followup question and cross questions.
    History of responses: '{history}'

    This is the last response of user - '{user_response}'

    And If a Question is completely answered by the user then say strictly say -> 1
    If the user is  completely clueless (cannot answer in 3 tries or followups )then say strictly say -> give -1
    And if followup question is about to be asked then just ask the followup question and dont give any SCORE.
    Response Must only contain One code block if any code is to be shared.
    Put normal text outside the code block.
    Strictly ask the user to write code , and avoid theoretical questions.

    You may be given code while user is writing code and you may choose to intervene or wait for user to complete or if he is going wrong way then you may give him any hint
    For intervention strictly just return 0
"""
    return text

history = [f"Preferred Language - {st.session_state.messages[0]['content']}"]

if audio:
    # Audio simulated input
    with st.spinner("Thinking..."):

        with open("temp_audio.wav", "wb") as f:
            f.write(audio.getbuffer())
        st.success("Audio recorded and saved successfully!")

        user_final = transcribe_audio()

        st.session_state.messages.append({"role": "user", "content": prompt})
        final_prompt = phraser(user_response=user_final)
        gemini_response_text = gemini_response(final_prompt)


        if gemini_response_text[0] == '1':
            if LEVEL==5:
                SCORE.append(LEVEL*2)
            else:
                SCORE.append(LEVEL*2)
                LEVEL += 1
            history = [f"Preferred Language - {st.session_state.messages[0]['content']}"]
        elif gemini_response_text[0] == '-1':
            if LEVEL==1:
                SCORE.append(0)
            else:
                LEVEL -= 1
                SCORE.append(0)
            history = [f"Preferred Language - {st.session_state.messages[0]['content']}"]

        else:
            response = gemini_response_text[0:gemini_response_text.find("```")]
            code = gemini_response_text[gemini_response_text.find("```")+3:gemini_response_text.rfind("```")]
            if code.strip():  
                st.session_state.code_content = code.strip()

            st.session_state.messages.append({"role": "assistant", "content": response})
            history.append({"role": "user", "content": user_final})
            history.append({"role": "assistant", "content": gemini_response_text})


        REMAINING_QUESTIONS -= 1
        if REMAINING_QUESTIONS <= 0:
            total_score = sum(SCORE)
            st.session_state.messages.append({"role": "assistant", "content": f"Interview Over! Your total  SCORE is {total_score} out of {10*LEVEL*2}."})
            prompt = None  

        st.rerun()
if prompt:
    # 1. Simulate an LLM response (THIS IS WHERE YOU'D CALL YOUR BACKEND)
    with st.spinner("Thinking..."):
        user_final = prompt

        st.session_state.messages.append({"role": "user", "content": prompt})
        final_prompt = phraser(user_response=user_final)
        gemini_response_text = gemini_response(final_prompt)


        if gemini_response_text[0] == '1':
            if LEVEL==5:
                SCORE.append(LEVEL*2)
            else:
                SCORE.append(LEVEL*2)
                LEVEL += 1
            history = [f"Preferred Language - {st.session_state.messages[0]['content']}"]
        elif gemini_response_text[0] == '-1':
            if LEVEL==1:
                SCORE.append(0)
            else:
                LEVEL -= 1
                SCORE.append(0)
            history = [f"Preferred Language - {st.session_state.messages[0]['content']}"]

        else:
            response = gemini_response_text[0:gemini_response_text.find("```")]
            code = gemini_response_text[gemini_response_text.find("```")+3:gemini_response_text.rfind("```")]
            if code.strip():  
                st.session_state.code_content = code.strip()

            st.session_state.messages.append({"role": "assistant", "content": response})
            history.append({"role": "user", "content": user_final})
            history.append({"role": "assistant", "content": gemini_response_text})

        REMAINING_QUESTIONS -= 1
        if REMAINING_QUESTIONS <= 0:
            total_score = sum(SCORE)
            st.session_state.messages.append({"role": "assistant", "content": f"Interview Over! Your total  SCORE is {total_score} out of {10*LEVEL*2}."})
            prompt = None  

    # Rerun the app to display the new messages and updated code
    st.rerun()



'''
if "thread_started" not in st.session_state and False:
    st.session_state.thread_started = True
    # daemon thread so that it stops when main app stops
    thread = threading.Thread(target=monitoring_bot, daemon=True)
    thread.start()
    print("🚀 Background saving thread started.")
'''

