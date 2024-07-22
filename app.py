import streamlit as st
import pandas as pd
import requests
import os
import zipfile
from io import BytesIO
from dotenv import load_dotenv
import PyPDF2 as pdf
import google.generativeai as genai

load_dotenv()  # Load all our environment variables

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# App1 functions
def get_gemini_response(input):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(input)
    return response.text

def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in range(len(reader.pages)):
        page = reader.pages[page]
        text += str(page.extract_text())
    return text.lower()  # Convert to lowercase for case-insensitive matching

input_prompt = """
Hey Act Like a skilled or very experience ATS(Application Tracking System)
with a deep understanding of tech field,software engineering,data science ,data analyst
and big data engineer. Your task is to evaluate the resume based on the given job description.
You must consider the job market is very competitive and you should provide 
best assistance for improving thr resumes. Assign the percentage Matching based 
on Jd and
the missing keywords with high accuracy
resume:{text}
description:{jd}

I want the response as per below structure
{{"JD Match": "%", "MissingKeywords": [], "Profile Summary": ""}}
"""

# App2 functions
def read_data(file, sheet_name=None):
    if file.type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        if sheet_name:
            df = pd.read_excel(file, sheet_name=sheet_name)
        else:
            sheet_names = pd.ExcelFile(file).sheet_names
            if len(sheet_names) == 1:
                df = pd.read_excel(file)
            else:
                selected_sheet = st.selectbox("Select Sheet", sheet_names)
                df = pd.read_excel(file, sheet_name=selected_sheet)
    elif file.type == 'text/csv':
        df = pd.read_csv(file)
    else:
        st.error("Invalid file format. Please upload an Excel (xlsx) or CSV file.")
        return None
    return df

def get_column_priorities(selected_cols):
    options = list(selected_cols)
    priorities = []
    for i in range(len(selected_cols)):
        priority = f"Priority {i+1}: "
        priority += st.selectbox("", options, key=f"priority_{i}")
        options.remove(priority.split(": ")[-1])  # Remove selected option
        priorities.append(priority)
    return priorities

def get_filter_options(df, priority_cols):
    filter_options = {}
    for col in priority_cols:
        options = df[col].unique().tolist()
        filter_options[col] = st.multiselect(col, options, key=f"filter_{col}")
    return filter_options

def filter_data(df, filter_options):
    filtered_df = df.copy()
    for col, options in filter_options.items():
        if options:
            filtered_df = filtered_df[filtered_df[col].isin(options)]
    return filtered_df

def download_pdf_from_drive(link, download_path):
    try:
        file_id = link.split("id=")[-1]
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        response = requests.get(url)
        if response.status_code == 200:
            with open(download_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            return False
    except Exception as e:
        return False

def create_zip_with_pdfs(pdf_paths, zip_path):
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for pdf in pdf_paths:
            zipf.write(pdf, os.path.basename(pdf))

# Main App
st.title("Applicant Management")

option = st.selectbox("Choose an Option", ["Excel Extractor", "Score Generator"])

if option == "Score Generator":
    st.title("Resume Applicant Score Generator")
    jd = st.text_area("Paste the Job Description")
    uploaded_file = st.file_uploader("Upload Your Resume", type="pdf", help="Please upload the pdf")
    submit = st.button("Submit")

    if submit:
        if uploaded_file is not None:
            text = input_pdf_text(uploaded_file)
            response = get_gemini_response(input_prompt.format(text=text, jd=jd))
            st.subheader(response)

elif option == "Excel Extractor":
    st.title("Streamlit File Explorer with Column Prioritization and Filtering")
    uploaded_file = st.file_uploader("Choose an Excel or CSV file", type=['csv', 'xlsx'])

    if uploaded_file is not None:
        df = read_data(uploaded_file)
        if df is not None:
            st.subheader("File Preview")
            st.write(df.head())

            selected_cols = st.multiselect("Select Columns", df.columns)
            if selected_cols:
                priorities = get_column_priorities(selected_cols.copy())
                st.subheader("Set Column Priorities")
                for priority in priorities:
                    st.write(priority)

                if priorities:
                    priority_cols = [p.split(": ")[-1] for p in priorities]
                    filter_options = get_filter_options(df.copy(), priority_cols)
                    st.subheader("Set Filters (Optional)")
                    for col, options in filter_options.items():
                        st.write(f"{col}:", options)

                    if all(not options for options in filter_options.values()):
                        st.error("Please select at least one filter option.")
                    else:
                        filtered_df = filter_data(df.copy(), filter_options)
                        st.subheader("Filtered Data Preview")
                        all_cols = df.columns.tolist()
                        st.write(filtered_df[all_cols].head())
                        st.download_button(
                            label="Download Filtered Data",
                            data=filtered_df.to_csv(),
                            file_name="filtered_data.csv",
                            mime="text/csv",
                        )

                        st.subheader("Download PDFs from Drive Links")
                        pdf_links = []

                        if "Share your Resume" in filtered_df.columns and "Full Name" in filtered_df.columns:
                            for _, row in filtered_df.iterrows():
                                link = row["Share your Resume"]
                                if link.startswith("https://drive.google.com/open?id="):
                                    pdf_links.append((link, row["Full Name"]))

                        st.write(f"Number of Drive links found: {len(pdf_links)}")
                        st.write(f"Number of PDFs found: {len(pdf_links)}")

                        if pdf_links:
                            pdf_dir = "pdfs"
                            os.makedirs(pdf_dir, exist_ok=True)
                            pdf_paths = []
                            total_pdfs = len(pdf_links)
                            pdfs_downloaded = 0

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            for i, (link, name) in enumerate(pdf_links):
                                pdf_path = os.path.join(pdf_dir, f"{name}.pdf")
                                if download_pdf_from_drive(link, pdf_path):
                                    pdf_paths.append(pdf_path)
                                    pdfs_downloaded += 1
                                    progress_bar.progress((pdfs_downloaded / total_pdfs))
                                    status_text.text(f"Downloaded {pdfs_downloaded}/{total_pdfs}")

                            st.write(f"Number of PDFs downloaded: {pdfs_downloaded}")

                            if pdf_paths:
                                zip_path = "pdf_documents.zip"
                                with st.spinner("Creating ZIP file..."):
                                    create_zip_with_pdfs(pdf_paths, zip_path)
                                with open(zip_path, 'rb') as f:
                                    st.download_button(
                                        label="Download ZIP with PDFs",
                                        data=f,
                                        file_name=zip_path,
                                        mime="application/zip",
                                    )

                                for pdf_path in pdf_paths:
                                    os.remove(pdf_path)
                                os.rmdir(pdf_dir)
                            else:
                                st.error("No PDFs were successfully downloaded.")
                        else:
                            st.error("No Drive links found in the filtered data.")
