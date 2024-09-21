import os
import streamlit as st
import requests
import pandas as pd

# BACKEND_URL = "http://34.93.43.213:8000"  
BACKEND_URL = os.getenv('BACKEND_URL_ENV')
print(f"backend: {BACKEND_URL}")  #

def main():
    st.title("Image Classification App")
    page = st.sidebar.selectbox("Choose a page", ["Upload", "History"])

    if page == "Upload":
        upload_page()
    elif page == "History":
        history_page()

def upload_page():
    st.header("Upload Images for Classification")
    uploaded_file = st.file_uploader("Choose an image file or ZIP", type=["jpg", "jpeg", "png", "zip"])

    if uploaded_file is not None:
        if st.button("Classify Images"):
            st.info("Uploading file... Please wait.")
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            
            try:
                response = requests.post(f"{BACKEND_URL}/upload", files=files, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"Task added to queue. Batch ID: {result['batch_id']}")
                else:
                    st.error(f"Error during upload: {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {str(e)}")

def history_page():
    st.header("Upload History")
    
    try:
        response = requests.get(f"{BACKEND_URL}/batches", timeout=10)
        if response.status_code == 200:
            batches = response.json()
            if batches:
                for batch in batches:
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    with col1:
                        st.write(f"Batch ID: {batch['batch_id']}")
                    with col2:
                        st.write(f"Upload Time: {batch['upload_time']}")
                    with col3:
                        st.write(f"Status: {batch['status']}")
                    with col4:
                        if st.button("Download CSV", key=f"btn_{batch['batch_id']}"):
                            download_batch_csv(batch['batch_id'])
            else:
                st.write("No batches found.")
        else:
            st.error(f"Failed to fetch batch history. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")

def download_batch_csv(batch_id):
    try:
        response = requests.get(f"{BACKEND_URL}/tasks/{batch_id}", timeout=10)
        if response.status_code == 200:
            batch_data = response.json()
            df = pd.DataFrame(batch_data['tasks'])
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"Download CSV for Batch {batch_id}",
                data=csv,
                file_name=f"batch_{batch_id}_results.csv",
                mime="text/csv",
                key=f"download_{batch_id}"
            )
        else:
            st.error(f"Failed to fetch batch data. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")

if __name__ == "__main__":
    main()