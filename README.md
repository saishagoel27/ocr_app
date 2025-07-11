# 📄 Financial Document Processor with AI Chat

A powerful web application that combines Azure Document Intelligence and Google Gemini AI to process financial documents with intelligent chat capabilities.

## 🌟 Features

### 📊 Document Processing
- **Azure AI Integration**: Advanced OCR and structured data extraction
- **Real-time Processing**: Instant document analysis with progress indicators

### 💬 AI Chat Integration
- **Interactive Chat**: Ask questions about your processed documents

### 🗄️ Data Management
- **SQLite Database**: Local storage for processed documents
- **CSV Export**: Export all processed data with structured formatting
- **Document History**: Track all processed documents with timestamps

### 🎨 User Interface
- **Streamlit Framework**: Clean, responsive web interface

##  Getting Started

### Prerequisites
- Python 3.8+
- Azure for Students account from https://azure.microsoft.com/en-us/free/students
- Google Gemini API from https://aistudio.google.com/

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd financial-document-processor
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install streamlit db-sqlite3 pandas python-dotenv azure-ai-documentintelligence google-generativeai
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=your_azure_endpoint
   AZURE_DOCUMENT_INTELLIGENCE_KEY=your_azure_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

### Running the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`


## 📁 Project Structure

```
financial-document-processor/
├── app.py                 # Main application file
├── .env                   # Environment variables (create this)
├── financial_docs.db     # SQLite database (auto-created)
├── requirements.txt      # Python dependencies
```

## 🛠️ Technical Details

### Dependencies
- **streamlit**: Web framework
- **azure-ai-documentintelligence**: Azure OCR service
- **google-generativeai**: Gemini AI integration
- **sqlite3**: Database management
- **pandas**: Data manipulation
- **python-dotenv**: Environment variable management


## 📄 License

This project is licensed under the MIT License - free to use and modify

**Built with ❤️ using Azure AI and Google Gemini**
