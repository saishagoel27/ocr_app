import streamlit as st
import sqlite3
import json
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import base64
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
import io
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Azure Document Intelligence configuration
AZURE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

# Gemini AI configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Database configuration
DATABASE_NAME = "financial_docs.db"

# Initialize Azure client
try:
    document_client = DocumentIntelligenceClient(
        endpoint=AZURE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_KEY)
    )
except Exception as e:
    st.error(f"Failed to initialize Azure client: {e}")
    document_client = None

# Initialize Gemini AI
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    else:
        gemini_model = None
        st.warning("Gemini API key not found. Chat functionality will be disabled.")
except Exception as e:
    st.error(f"Failed to initialize Gemini AI: {e}")
    gemini_model = None

# Streamlit page configuration
st.set_page_config(
    page_title="Financial Document Processor with AI Chat",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Financial Document Processor with AI Chat")
st.write("Upload your financial documents (PDF, JPG, PNG) to extract key information using Azure AI and chat with them using Gemini!")

# Initialize session state
if 'processing_result' not in st.session_state:
    st.session_state.processing_result = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_document_context' not in st.session_state:
    st.session_state.current_document_context = None

# Database functions
def init_database():
    """Initialize SQLite database with required table"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_timestamp TEXT NOT NULL,
                raw_text TEXT,
                structured_data TEXT,
                model_type TEXT,
                file_size INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database initialization error: {e}")
        return False

def save_to_database(filename, raw_text, structured_data, model_type, file_size):
    """Save document processing results to database"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Insert data
        cursor.execute('''
            INSERT INTO document_results 
            (filename, upload_timestamp, raw_text, structured_data, model_type, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            datetime.now().isoformat(),
            raw_text,
            json.dumps(structured_data),
            model_type,
            file_size
        ))
        
        conn.commit()
        conn.close()
        return True, "Data saved successfully!"
    except Exception as e:
        return False, f"Database save error: {e}"

def get_all_records():
    """Retrieve all records from database"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        df = pd.read_sql_query("SELECT * FROM document_results ORDER BY upload_timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database read error: {e}")
        return pd.DataFrame()

def get_records_count():
    """Get total number of records in database"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM document_results")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        return 0

def prepare_csv_export():
    """Prepare data for CSV export with flattened structured data"""
    try:
        df = get_all_records()
        if df.empty:
            return None
        
        # Create a new dataframe for export
        export_data = []
        
        for _, row in df.iterrows():
            # Start with basic fields
            export_row = {
                'ID': row['id'],
                'Filename': row['filename'],
                'Upload_Timestamp': row['upload_timestamp'],
                'Model_Type': row['model_type'],
                'File_Size_Bytes': row['file_size'],
                'Raw_Text_Length': len(row['raw_text']) if row['raw_text'] else 0
            }
            
            # Parse and flatten structured data
            try:
                structured_data = json.loads(row['structured_data']) if row['structured_data'] else {}
                
                # Add common fields with prefixes
                for key, value in structured_data.items():
                    if isinstance(value, dict):
                        # Handle currency fields
                        if 'value' in value and 'currency' in value:
                            export_row[f'Extracted_{key}_Amount'] = value.get('value')
                            export_row[f'Extracted_{key}_Currency'] = value.get('currency')
                        else:
                            export_row[f'Extracted_{key}'] = str(value)
                    else:
                        export_row[f'Extracted_{key}'] = value
                
            except json.JSONDecodeError:
                export_row['Structured_Data_Error'] = 'JSON parsing failed'
            
            # Add raw text (truncated for CSV)
            if row['raw_text']:
                export_row['Raw_Text_Preview'] = row['raw_text'][:500] + '...' if len(row['raw_text']) > 500 else row['raw_text']
            else:
                export_row['Raw_Text_Preview'] = ''
            
            export_data.append(export_row)
        
        return pd.DataFrame(export_data)
    
    except Exception as e:
        st.error(f"CSV preparation error: {e}")
        return None

# Gemini AI chat functions
def create_document_context(filename, raw_text, structured_data):
    """Create a context string for the document to use with Gemini"""
    context = f"""
Document Information:
- Filename: {filename}
- Document Type: Financial Document

Raw Text Content:
{raw_text}

Structured Data Extracted:
{json.dumps(structured_data, indent=2)}

You are an AI assistant that helps users understand and analyze financial documents. 
The user has uploaded the document shown above. Please answer questions about this document 
based on the content provided. Be helpful, accurate, and focus on the financial aspects.
"""
    return context

def chat_with_gemini(user_message, document_context):
    """Send message to Gemini AI with document context"""
    try:
        if not gemini_model:
            return "Gemini AI is not available. Please check your API key."
        
        # Prepare the prompt with context
        full_prompt = f"{document_context}\n\nUser Question: {user_message}\n\nPlease provide a helpful answer based on the document content above."
        
        # Generate response
        response = gemini_model.generate_content(full_prompt)
        return response.text
    
    except Exception as e:
        return f"Error generating response: {str(e)}"

# Function to validate file type
def is_valid_file(file):
    """Check if uploaded file is a supported format"""
    allowed_types = ['pdf', 'jpg', 'jpeg', 'png']
    if file is not None:
        file_extension = file.name.split('.')[-1].lower()
        return file_extension in allowed_types
    return False

def get_content_type(filename):
    """Get the content type for Azure API based on file extension"""
    extension = filename.split('.')[-1].lower()
    content_types = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png'
    }
    return content_types.get(extension, 'application/octet-stream')

# Azure processing function
def process_document_with_azure(uploaded_file, model_type="Invoice"):
    """Process document using Azure Document Intelligence"""
    try:
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        
        model_mapping = {
            "Invoice": "prebuilt-invoice",
            "Receipt": "prebuilt-receipt", 
            "General Document": "prebuilt-read",
        }
        
        actual_model_id = model_mapping.get(model_type, "prebuilt-read")
        
        poller = document_client.begin_analyze_document(
            model_id=actual_model_id,
            body=file_content,
            content_type=get_content_type(uploaded_file.name)
        )
        
        result = poller.result()
        
        # Extract raw text
        raw_text = ""
        if hasattr(result, 'content') and result.content:
            raw_text = result.content
        
        # Extract structured data
        structured_data = {}
        
        if hasattr(result, 'documents') and result.documents:
            doc = result.documents[0]
            
            if hasattr(doc, 'fields') and doc.fields:
                for field_name, field_value in doc.fields.items():
                    if field_value and hasattr(field_value, 'value') and field_value.value is not None:
                        if hasattr(field_value, 'value_type'):
                            if field_value.value_type == "currency":
                                if hasattr(field_value.value, 'amount') and hasattr(field_value.value, 'currency_code'):
                                    structured_data[field_name] = {
                                        "value": field_value.value.amount,
                                        "currency": field_value.value.currency_code
                                    }
                                else:
                                    structured_data[field_name] = str(field_value.value)
                            elif field_value.value_type == "date":
                                structured_data[field_name] = str(field_value.value)
                            else:
                                structured_data[field_name] = field_value.value
                        else:
                            structured_data[field_name] = field_value.value
        
        return True, raw_text, structured_data, None
        
    except AzureError as e:
        return False, "", {}, f"Azure API Error: {str(e)}"
    except Exception as e:
        return False, "", {}, f"Processing Error: {str(e)}"

def display_structured_data(data):
    """Display structured data in a nice format"""
    if not data:
        st.warning("No structured data extracted")
        return
    
    st.subheader("📊 Extracted Key Information")
    
    for field_name, field_value in data.items():
        if isinstance(field_value, dict):
            if 'value' in field_value and 'currency' in field_value:
                st.write(f"• **{field_name}:** {field_value['value']} {field_value['currency']}")
            else:
                st.write(f"• **{field_name}:** {field_value}")
        else:
            st.write(f"• **{field_name}:** {field_value}")

# Initialize database
if init_database():
    records_count = get_records_count()
else:
    records_count = 0

# Main upload section
st.header("📤 Upload Document")

model_type = st.selectbox(
    "Choose document type:",
    ["Invoice", "Receipt", "General Document"],
    help="Select the type of document you're uploading for better accuracy"
)

uploaded_file = st.file_uploader(
    "Choose a financial document (PDF, JPG, PNG)",
    type=['pdf', 'jpg', 'jpeg', 'png'],
    help="Upload invoices, receipts, or other financial documents"
)

# Process uploaded file
if uploaded_file is not None:
    if is_valid_file(uploaded_file):
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Filename:** {uploaded_file.name}")
        with col2:
            st.write(f"**Size:** {uploaded_file.size} bytes")
        with col3:
            st.write(f"**Type:** {uploaded_file.type}")
        
        if uploaded_file.type.startswith('image/'):
            st.subheader("📸 Preview")
            st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)
        
        # Process button
        if st.button("🔍 Process Document", type="primary"):
            if document_client:
                with st.spinner("Processing document with Azure AI... Please wait."):
                    success, raw_text, structured_data, error_msg = process_document_with_azure(
                        uploaded_file, model_type
                    )
                    
                    if success:
                        st.success("✅ Document processed successfully!")
                        
                        # Store in session state
                        st.session_state.processing_result = {
                            'filename': uploaded_file.name,
                            'raw_text': raw_text,
                            'structured_data': structured_data,
                            'model_type': model_type,
                            'file_size': uploaded_file.size
                        }
                        
                        # Create document context for Gemini
                        st.session_state.current_document_context = create_document_context(
                            uploaded_file.name, raw_text, structured_data
                        )
                        
                        # Clear previous chat history when new document is processed
                        st.session_state.chat_history = []
                        
                        # Display results
                        tab1, tab2, tab3 = st.tabs(["📊 Structured Data", "📝 Raw Text", "💬 Chat with Document"])
                        
                        with tab1:
                            display_structured_data(structured_data)
                        
                        with tab2:
                            st.subheader("📝 Extracted Text (OCR)")
                            if raw_text:
                                st.text_area("Full text content:", raw_text, height=300)
                            else:
                                st.warning("No text content extracted")
                        
                        with tab3:
                            st.subheader("💬 Chat with Your Document")
                            if gemini_model:
                                st.info("Ask questions about your document! Examples: 'What is the total amount?', 'Who is the vendor?', 'What is the invoice date?'")
                                
                                # Chat interface placeholder
                                st.write("Chat functionality is ready! Use the chat section below after processing.")
                            else:
                                st.error("Gemini AI not available. Please check your API key.")
                    
                    else:
                        st.error(f"❌ Processing failed: {error_msg}")
            else:
                st.error("Azure client not available. Check your credentials.")
    else:
        st.error("❌ Invalid file type. Please upload PDF, JPG, or PNG files only.")

# Chat Interface Section
if st.session_state.current_document_context and gemini_model:
    st.header("💬 Chat with Your Document")
    
    # Display chat history
    for i, (question, answer) in enumerate(st.session_state.chat_history):
        with st.container():
            st.write(f"**🙋 You:** {question}")
            st.write(f"**🤖 AI:** {answer}")
            st.divider()
    
    # Chat input
    user_question = st.text_input(
        "Ask a question about your document:",
        placeholder="e.g., What is the total amount? Who is the vendor?",
        key="chat_input"
    )
    
    col_ask, col_clear = st.columns([1, 4])
    
    with col_ask:
        if st.button("Ask 🚀", type="primary"):
            if user_question.strip():
                with st.spinner("Thinking..."):
                    response = chat_with_gemini(user_question, st.session_state.current_document_context)
                    
                    # Add to chat history
                    st.session_state.chat_history.append((user_question, response))
                    
                    # Clear input and refresh
                    st.rerun()
            else:
                st.warning("Please enter a question!")
    
    with col_clear:
        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()

# Save to database section
if st.session_state.processing_result is not None:
    st.subheader("💾 Save Results")
    
    result = st.session_state.processing_result
    st.info(f"Ready to save: {result['filename']}")
    
    col_save1, col_save2 = st.columns([1, 3])
    
    with col_save1:
        if st.button("💾 Save to Database", type="secondary", key="save_btn"):
            save_success, save_message = save_to_database(
                result['filename'],
                result['raw_text'],
                result['structured_data'],
                result['model_type'],
                result['file_size']
            )
            
            if save_success:
                st.success(save_message)
                st.session_state.processing_result = None
                st.rerun()
            else:
                st.error(save_message)
    
    with col_save2:
        st.info("Click 'Save to Database' to store these results for later reference and CSV export.")

# Database section - FIXED CSV EXPORT
st.header("🗄️ Stored Results")

records_count = get_records_count()

if records_count > 0:
    st.success(f"📊 Total stored documents: **{records_count}**")
    
    col_view, col_export = st.columns(2)
    
    with col_view:
        if st.button("👁️ View All Records"):
            df = get_all_records()
            if not df.empty:
                st.subheader("📋 All Processing Results")
                display_df = df[['id', 'filename', 'upload_timestamp', 'model_type', 'file_size']].copy()
                display_df['upload_timestamp'] = pd.to_datetime(display_df['upload_timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                display_df['file_size'] = display_df['file_size'].apply(lambda x: f"{x} bytes")
                st.dataframe(display_df, use_container_width=True)
    
    with col_export:
        if st.button("📥 Export to CSV", type="secondary"):
            export_df = prepare_csv_export()
            if export_df is not None and not export_df.empty:
                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"financial_documents_export_{timestamp}.csv"
                
                # Create download button
                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV File",
                    data=csv,
                    file_name=filename,
                    mime="text/csv",
                    type="primary"
                )
                
                # Show preview of export data
                st.subheader("📊 Export Preview")
                st.write(f"**Columns included:** {len(export_df.columns)}")
                st.write(f"**Records to export:** {len(export_df)}")
                
                # Show first few rows
                st.dataframe(export_df.head(), use_container_width=True)
                
                st.success(f"✅ CSV export ready! File: `{filename}`")
            else:
                st.error("❌ No data available for export")

else:
    st.info("🔍 No documents processed yet. Upload and process a document to see results here.")

# Sidebar
if document_client:
    st.sidebar.success("✅ Azure Connected")
else:
    st.sidebar.error("❌ Azure Disconnected")

if gemini_model:
    st.sidebar.success("✅ Gemini AI Connected")
else:
    st.sidebar.error("❌ Gemini AI Disconnected")

st.sidebar.header("🗄️ Database Info")
st.sidebar.write(f"📊 Stored Records: **{records_count}**")
st.sidebar.write(f"💾 Database: `{DATABASE_NAME}`")

st.sidebar.header("🤖 AI Features")
st.sidebar.write("• **Azure Document Intelligence** - OCR & Data Extraction")
st.sidebar.write("• **Gemini AI** - Interactive Document Chat")

st.sidebar.header("💬 Chat Examples")
st.sidebar.write("• What is the total amount?")
st.sidebar.write("• Who is the vendor?")
st.sidebar.write("• What is the invoice date?")
st.sidebar.write("• Summarize this document")
st.sidebar.write("• Find any discrepancies")

st.sidebar.header("📋 Supported Formats")
st.sidebar.write("• PDF")
st.sidebar.write("• JPG/JPEG")
st.sidebar.write("• PNG")
