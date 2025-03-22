from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import PyPDF2
import re
from transformers import pipeline

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Load models
summarizer = pipeline("summarization", model="t5-large")
qa_pipeline = pipeline("text2text-generation", model="valhalla/t5-base-qg-hl")

# NEW: BERT Question Answering Pipeline (Extractive QA)
answer_pipeline = pipeline(
    "question-answering",
    model="bert-large-uncased-whole-word-masking-finetuned-squad",
    tokenizer="bert-large-uncased-whole-word-masking-finetuned-squad"
)

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

    text = re.sub(r"Page \d+", "", text)       # Remove page numbers
    text = re.sub(r"\.{2,}", ".", text)        # Reduce consecutive dots
    text = re.sub(r"[^a-zA-Z0-9\s.,-]", " ", text)  # Remove odd symbols
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
    """Summarizes text while enforcing a word limit."""
    text_chunks = split_text_into_chunks(text, max_tokens=500)
    summarized_chunks = []

    if summary_type == "short":
        max_len = 100
        min_len = 50
        word_limit = 150  # final truncated words
    else:
        max_len = 300
        min_len = 150
        word_limit = 1000

    for chunk in text_chunks:
        summary = summarizer(
            chunk, max_length=max_len, min_length=min_len, do_sample=False
        )[0]["summary_text"]
        summarized_chunks.append(summary)

    # Join partial summaries into one
    final_summary = " ".join(summarized_chunks)
    final_summary_words = final_summary.split()
    if len(final_summary_words) > word_limit:
        final_summary = " ".join(final_summary_words[:word_limit]) + "..."

    return final_summary

def generate_questions(text):
    """Generates up to 10 questions from the text safely using the T5-based QG model."""
    text_chunks = split_text_into_chunks(text, max_tokens=256)
    generated_questions = []

    for chunk in text_chunks:
        # "qa_pipeline" is actually the question-generation pipeline in this code
        questions = qa_pipeline(chunk, max_length=100)
        generated_questions.extend(q["generated_text"] for q in questions)

        if len(generated_questions) >= 10:
            break

    return generated_questions[:10]

def generate_answers(questions, text):
    """
    For each question, use the BERT QA pipeline to extract the best possible answer
    from the text. This is extractive QA, so it picks a span from the original text.
    """
    answers = []
    for q in questions:
        try:
            result = answer_pipeline(question=q, context=text)
            answers.append(result["answer"])
        except Exception as e:
            answers.append(f"Error generating answer: {str(e)}")
    
    return answers

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

        # Extract text from the uploaded PDF
        text = extract_text(filepath)
        if not text.strip():
            return jsonify({"error": "Extracted text is empty. Ensure the file contains readable text."}), 400

        print("\n===== Extracted Text (First 500 chars) =====")
        print(text[:500])

        # Determine summary type from the frontend or default to "short"
        summary_type = request.form.get("summary_type", "short")
        print(f"Summary type selected: {summary_type}")

        # Summarize the entire text
        summary = summarize_text(text, summary_type)

        # Generate top 10 questions from the text
        print("\n===== Calling Question Generation Model =====")
        questions = generate_questions(text)

        print("\n===== Questions Generated =====")
        for q in questions:
            print(q)

        # Generate answers using BERT QA for each question
        print("\n===== Generating Answers with BERT QA =====")
        answers = generate_answers(questions, text)

        # Print answers for debug
        for ans in answers:
            print(ans)

        # Return summary, questions, and answers
        return jsonify({"summary": summary, "questions": questions, "answers": answers})

    except Exception as e:
        print("\n===== ERROR OCCURRED =====")
        print(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
