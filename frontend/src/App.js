import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import jsPDF from "jspdf";
import "./styles.css";

const App = () => {
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState("");
  const [fullText, setFullText] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [qaLoading, setQaLoading] = useState(false);
  const [summaryType, setSummaryType] = useState("short");
  const fileInputRef = useRef(null);
  const [keywords, setKeywords] = useState([]);
  const [videos, setVideos] = useState([]);
  const [voices, setVoices] = useState([]);
  const [selectedLang, setSelectedLang] = useState("en-US");

  useEffect(() => {
    const loadVoices = () => {
      const allVoices = window.speechSynthesis.getVoices();
      setVoices(allVoices);
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, []);

  const fetchVideos = async (keywords) => {
    if (!keywords.length) return;
    const query = keywords.join(" ");
    const API_KEY = "Your API Key";

    try {
      const res = await axios.get("https://www.googleapis.com/youtube/v3/search", {
        params: {
          q: query,
          part: "snippet",
          maxResults: 5,
          type: "video",
          key: API_KEY
        }
      });
      setVideos(res.data.items);
    } catch (err) {
      console.error("Video fetch error:", err);
    }
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return alert("Please select a file");

    setLoading(true);
    setQaLoading(false);
    setSummary("");
    setQuestions([]);
    setAnswers([]);
    setKeywords([]);
    setVideos([]);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("summary_type", summaryType);

    try {
      const response = await axios.post("http://127.0.0.1:5000/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const { summary, full_text } = response.data;
      setSummary(summary);
      setFullText(full_text);

      // Fetch Q&A using new /result POST route
      fetchQA(full_text, summary);
    } catch (error) {
      console.error("Upload error:", error.response ? error.response.data : error);
      alert("Error uploading file. Check console for details.");
    } finally {
      setLoading(false);
    }
  };

  const fetchQA = async (fullText, summaryText) => {
    setQaLoading(true);
    try {
      const res = await axios.post("http://127.0.0.1:5000/result", {
        full_text: fullText,
        summary: summaryText
      });

      setQuestions(res.data.questions);
      setAnswers(res.data.answers);
      setKeywords(res.data.keywords);
      fetchVideos(res.data.keywords);
    } catch (err) {
      console.error("QA generation error:", err);
      alert("Error generating Q&A.");
    } finally {
      setQaLoading(false);
    }
  };

  const speakText = (text) => {
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = voices.find(v => v.lang === selectedLang);
    if (voice) utterance.voice = voice;
    utterance.lang = selectedLang;
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  };

  const handleDownloadPDF = () => {
    const doc = new jsPDF();
    let y = 10;

    doc.setFontSize(16);
    doc.text("SmartStudy AI - Summary & Q&A", 10, y);
    y += 10;

    doc.setFontSize(12);
    doc.text("Summary:", 10, y);
    y += 8;
    const summaryLines = doc.splitTextToSize(summary, 180);
    doc.text(summaryLines, 10, y);
    y += summaryLines.length * 6 + 5;

    if (questions.length > 0 && answers.length > 0) {
      doc.text("Questions & Answers:", 10, y);
      y += 8;

      questions.forEach((q, i) => {
        if (y > 270) {
          doc.addPage();
          y = 10;
        }
        const questionLines = doc.splitTextToSize(`Q${i + 1}: ${q}`, 180);
        const answerLines = doc.splitTextToSize(`A${i + 1}: ${answers[i]}`, 180);
        doc.text(questionLines, 10, y);
        y += questionLines.length * 6;
        doc.text(answerLines, 10, y);
        y += answerLines.length * 6 + 4;
      });
    }
    doc.save("SmartStudy_Summary_QA.pdf");
  };

  return (
    <div className="container">
      <h1 className="title">SmartStudy AI</h1>

      <div className="upload-area" onClick={() => fileInputRef.current.click()}>
        {file ? <p className="file-selected">Selected: {file.name}</p> : <p className="upload-text">Click to Upload or Drag & Drop</p>}
        <input type="file" ref={fileInputRef} onChange={handleFileChange} className="file-input" />
      </div>

      <div className="summary-options">
        <label htmlFor="summaryType" className="summary-label">Select Summary Type:</label>
        <select id="summaryType" className="summary-dropdown" value={summaryType} onChange={(e) => setSummaryType(e.target.value)}>
          <option value="short">Short Summary</option>
          <option value="long">Long Summary</option>
        </select>
      </div>

      <button className="upload-button" onClick={handleUpload} disabled={loading}>
        {loading ? "Processing..." : "Upload & Analyze"}
      </button>

      {summary && (
        <div className="summary-section">
          <h2 className="subtitle">Summary</h2>
          <pre className="summary-text">{summary}</pre>
          <div>
            <button className="download-button" onClick={handleDownloadPDF}>📄 Download PDF</button>
          </div>
        </div>
      )}

      {qaLoading && (
        <div className="questions-section">
          <h2 className="subtitle">Generating Questions & Answers...</h2>
        </div>
      )}

      {questions.length > 0 && answers.length > 0 && !qaLoading && (
        <div className="questions-section">
          <h2 className="subtitle">Generated Q&A</h2>
          <ul className="question-list">
            {questions.map((question, index) => (
              <li key={index}>
                <strong>Q{index + 1}: {question}</strong>
                <br />
                <span><strong>A{index + 1}:</strong> {answers[index]}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {videos.length > 0 && (
        <div className="video-section">
          <h2 className="subtitle">🎥 Recommended Videos</h2>
          <div className="video-grid">
            {videos.map((video, index) => (
              <a
                key={index}
                href={`https://www.youtube.com/watch?v=${video.id.videoId}`}
                target="_blank"
                rel="noreferrer"
                className="video-card"
              >
                <img
                  src={video.snippet.thumbnails.medium.url}
                  alt={video.snippet.title}
                  className="video-thumbnail"
                />
                <div className="video-info">
                  <p className="video-title">{video.snippet.title}</p>
                  <p className="video-channel">{video.snippet.channelTitle}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
