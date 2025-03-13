import React, { useState, useRef } from "react";
import axios from "axios";
import "./styles.css";

const App = () => {
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState("");
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [summaryType, setSummaryType] = useState("short");
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) return alert("Please select a file");
  
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("summary_type", summaryType);
  
    try {
      const response = await axios.post("http://127.0.0.1:5000/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
  
      console.log("API Response:", response.data);
      setSummary(response.data.summary);
      setQuestions(response.data.questions);
  
      // 🔹 Scroll to top to make sure the upload area is visible
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      console.error("Upload error:", error.response ? error.response.data : error);
      alert("Error uploading file. Check console for details.");
    } finally {
      setLoading(false);
    }
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
        </div>
      )}

      {questions.length > 0 && (
        <div className="questions-section">
          <h2 className="subtitle">Generated Questions</h2>
          <ul className="question-list">
            {questions.map((q, index) => (
              <li key={index}>{q}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default App;
