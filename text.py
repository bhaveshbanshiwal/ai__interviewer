import streamlit as st

st.title("Record Your Audio")

# Use the built-in audio input widget to record from mic
audio = st.audio_input("Record your audio")

if audio:
    # Save the recorded audio buffer to a file
    with open("recorded_audio.wav", "wb") as f:
        f.write(audio.getbuffer())
    st.success("Audio recorded and saved successfully!")