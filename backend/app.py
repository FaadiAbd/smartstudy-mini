from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import PyPDF2
import re
from transformers import pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Load models
summarizer = pipeline("summarization", model="t5-large")
qa_pipeline = pipeline("text2text-generation", model="valhalla/t5-base-qg-hl")
answer_pipeline = pipeline(
    "question-answering",
    model="bert-large-uncased-whole-word-masking-finetuned-squad",
    tokenizer="bert-large-uncased-whole-word-masking-finetuned-squad"
)

def extract_text(filepath):
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
    text_chunks = split_text_into_chunks(text, max_tokens=500)
    summarized_chunks = []
    if summary_type == "short":
        max_len = 100
        min_len = 50
        word_limit = 150
    else:
        max_len = 300
        min_len = 150
        word_limit = 1000
    for chunk in text_chunks:
        summary = summarizer(chunk, max_length=max_len, min_length=min_len, do_sample=False)[0]["summary_text"]
        summarized_chunks.append(summary)
    final_summary = " ".join(summarized_chunks)
    final_summary_words = final_summary.split()
    if len(final_summary_words) > word_limit:
        final_summary = " ".join(final_summary_words[:word_limit]) + "..."
    return final_summary

def generate_questions(text):
    text_chunks = split_text_into_chunks(text, max_tokens=256)
    generated_questions = []
    
    for chunk in text_chunks:
        try:
            questions = qa_pipeline(chunk, max_length=100)
            for q in questions:
                if q["generated_text"] not in generated_questions:
                    generated_questions.append(q["generated_text"])
            if len(generated_questions) >= 10:  # still keep an upper limit
                break
        except Exception as e:
            continue

   
    

    return generated_questions[:10]

def generate_answers(questions, text):
    answers = []
    for q in questions:
        try:
            result = answer_pipeline(question=q, context=text)
            answers.append(result["answer"])
        except Exception as e:
            answers.append(f"Error generating answer: {str(e)}")
    return answers

def extract_keywords(text, top_n=5):
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    tfidf_matrix = vectorizer.fit_transform([text])
    feature_array = vectorizer.get_feature_names_out()
    tfidf_scores = tfidf_matrix.toarray().flatten()
    top_indices = tfidf_scores.argsort()[::-1][:top_n]
    keywords = [feature_array[i] for i in top_indices]
    return keywords

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

        text = extract_text(filepath)
        if not text.strip():
            return jsonify({"error": "Extracted text is empty."}), 400

        summary_type = request.form.get("summary_type", "short")
        summary = summarize_text(text, summary_type)

        return jsonify({"summary": summary, "full_text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/result", methods=["POST"])
def generate_result():
    try:
        data = request.get_json()
        full_text = data.get("full_text", "")
        summary = data.get("summary", "")

        if not full_text or not summary:
            return jsonify({"error": "Full text or summary missing."}), 400

        questions = generate_questions(full_text)
        answers = generate_answers(questions, full_text)
        keywords = extract_keywords(full_text)

        return jsonify({
            "questions": questions,
            "answers": answers,
            "keywords": keywords
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
