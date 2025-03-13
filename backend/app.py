from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import PyPDF2
from transformers import pipeline
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
qa_pipeline = pipeline("text2text-generation", model="valhalla/t5-base-qg-hl")

def extract_text(filepath):
    """Extracts clean text from a PDF."""
    text = ""

    if filepath.endswith(".pdf"):
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

    text = re.sub(r"Page \d+", "", text)  
    text = re.sub(r"\.{2,}", ".", text)  
    text = re.sub(r"[^a-zA-Z0-9\s.,-]", " ", text)  
    text = re.sub(r"\s+", " ", text).strip()  

    return text

def split_text_into_chunks(text, max_tokens=400):
    """Splits long text into smaller chunks for processing."""
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if len(current_chunk) >= max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def summarize_text(text, summary_type):
    """Summarizes text based on the selected type."""
    text_chunks = split_text_into_chunks(text, max_tokens=500)
    summarized_chunks = []

    # Adjust max_length based on summary type
    if summary_type == "short":
        max_len = 100
        min_len = 50
    else:
        max_len = 300
        min_len = 150

    for chunk in text_chunks:
        summary = summarizer(chunk, max_length=max_len, min_length=min_len, do_sample=False)[0]["summary_text"]
        summarized_chunks.append(summary)

    final_summary = " ".join(summarized_chunks)
    return final_summary

def generate_questions(text):
    """Generates questions from the text safely."""
    text_chunks = split_text_into_chunks(text, max_tokens=256)  # Limit length for model
    generated_questions = []

    for chunk in text_chunks:
        questions = qa_pipeline(chunk, max_length=100)  # Prevent exceeding model limits
        generated_questions.extend(q["generated_text"] for q in questions)

    return generated_questions

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Extract text
        text = extract_text(filepath)
        if not text.strip():
            return jsonify({"error": "Extracted text is empty. Ensure the file contains readable text."}), 400

        # Debugging logs
        print("\n===== Extracted Text (First 500 chars) =====")
        print(text[:500])

        # Get summary type
        summary_type = request.form.get("summary_type", "short")
        print(f"Summary type selected: {summary_type}")

        summary = summarize_text(text, summary_type)

        print("\n===== Calling Question Generation Model =====")
        questions = generate_questions(text)

        print("\n===== Questions Generated =====")
        for q in questions:
            print(q)

        return jsonify({"summary": summary, "questions": questions})

    except Exception as e:
        print("\n===== ERROR OCCURRED =====")
        print(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
