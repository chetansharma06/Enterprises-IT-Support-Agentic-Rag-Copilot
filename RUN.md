# Enterprise IT Support Agentic RAG Copilot - Run and Debug Guide

This document provides comprehensive instructions on how to run, test, and debug the Enterprise IT Support Agentic RAG Copilot project.

## Project Overview

This is an end-to-end Forward Deployed Engineer (FDE) project that implements an Agentic RAG workflow for enterprise IT support using:
- **LangGraph** for stateful routing and conditional decisions
- **Groq** LLM for routing, grading, and query rewriting
- **Google Gemini** LLM for answer generation
- **FastAPI** for the backend API
- **Pinecone** as the vector database for private knowledge storage
- **HuggingFace sentence-transformers/all-MiniLM-L6-v2** for local embeddings
- **Tavily** for external web search as fallback
- **HTML/CSS/JavaScript** for the frontend UI
- **SQLite** for audit logging

## Prerequisites

### Software Requirements
- Python 3.11+ (tested with 3.11.9)
- pip (Python package manager)
- Git (optional, for version control)

### API Keys Required
You need to obtain API keys for the following services:
1. **Groq API** - For LLM operations (routing, grading, query rewriting)
2. **Google Gemini API** - For final answer generation from retrieved evidence
3. **Tavily API** - For external web search (fallback)
4. **Pinecone API** - For vector database storage

#### How to Obtain Free API Keys:
- **Groq**: Sign up at [groq.com](https://groq.com) for a free account with API credits
- **Gemini**: Get a free API key at [makersuite.google.com](https://makersuite.google.com) (includes free tier)
- **Tavily**: Sign up at [tavily.com](https://tavily.com) for a free API key (1,000 free searches/month)
- **Pinecone**: Register at [pinecone.io](https://www.pinecone.io) for a free serverless index (1G vector storage free tier)

## Setup Instructions

### 1. Clone/Download the Project
If you haven't already, obtain the project files. The project structure should look like:
```
Enterprise-IT-Support-Agentic-RAG-Copilot-main/
├── app/
│   ├── api/
│   ├── core/
│   ├── rag/
│   └── services/
├── data/
│   └── sample_kb/
├── static/
│   ├── css/
│   └── js/
├── templates/
├── uploads/
├── .env
├── Dockerfile
├── ingest_sample_kb.py
├── requirements.txt
├── run.py
└── README.md
```

### 2. Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv .venv

# Activation is optional after opening this workspace in VS Code: the selected
# `.venv` is auto-activated in new integrated terminals. These are fallback commands.
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the provided `.env.example` to `.env` (if it doesn't exist) and fill in your API keys:

```env
# LLM API Keys
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# External Search
TAVILY_API_KEY=your_tavily_api_key_here

# Vector Database (Pinecone)
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=fde-it-support-rag
PINECONE_NAMESPACE=company-it-kb

# Model Configuration
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Security
ADMIN_API_KEY=change-me-in-production

# Application Settings
APP_ENV=development
```

> **Note**: The `.env` file already contains sample keys in this repository. Replace them with your actual keys for production use.

#### How to Obtain Free API Keys:
- **Groq**: Sign up at [groq.com](https://groq.com) for a free account with API credits
- **Gemini**: Get a free API key at [makersuite.google.com](https://makersuite.google.com) (includes free tier)
- **Tavily**: Sign up at [tavily.com](https://tavily.com) for a free API key (1,000 free searches/month)
- **Pinecone**: Register at [pinecone.io](https://www.pinecone.io) for a free serverless index (1G vector storage free tier)

### 5. Load Sample Knowledge Base
The project includes sample IT documents that need to be indexed into Pinecone:
```bash
python ingest_sample_kb.py
```

This script will:
- Load the sample Markdown files from `data/sample_kb/`
- Chunk them into appropriate sizes
- Generate embeddings locally using HuggingFace sentence-transformers
- Store the vectors in Pinecone

Expected output:
```
Indexed 2 files -> X chunks -> X Pinecone vectors
```

### 6. Start the Application
```bash
python run.py
```

The application will start on `http://127.0.0.1:8080` (or the port specified in your environment).

Alternative startup methods:
```bash
# Using uvicorn directly
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

# Using Docker (see Docker section below)
docker build -t enterprise-it-support-copilot .
docker run -p 8080:8080 enterprise-it-support-copilot
```

## API Endpoints

Once the server is running, you can access:

### Health Check
- **URL**: `GET http://127.0.0.1:8080/api/health`
- **Response**: `{"status": "ok", "service": "Enterprise IT Support Agentic RAG Copilot"}`

### Chat Endpoint
- **URL**: `POST http://127.0.0.1:8080/api/chat`
- **Request Body**: `{"question": "Your IT support question here"}`
- **Response**: 
```json
{
  "answer": "The generated answer...",
  "source_used": "private_kb|web_search|direct|insufficient_evidence",
  "trace": ["Router → KB", "Private KB retrieval → 4 chunks", ...],
  "citations": [{"title": "Document Name", "url": "", "type": "private_kb"}],
  "rewritten_query": "Optional rewritten query if retries occurred"
}
```

### Document Upload (Admin Protected)
- **URL**: `POST http://127.0.0.1:8080/api/ingest`
- **Headers**: `X-Admin-Key: your_admin_api_key`
- **Form Data**: `file: [PDF/TXT/MD/DOCX file]`
- **Response**: 
```json
{
  "message": "Document indexed",
  "file": "filename.pdf",
  "chunks": 5,
  "ids_created": 5
}
```

## Using the Web Interface

Open your browser to `http://127.0.0.1:8080` to access the full UI:

### Features:
1. **Chat Interface**: Ask IT support questions
2. **Example Questions**: Click buttons to try predefined questions
3. **Agent Trace Panel**: Watch the LangGraph workflow execute in real-time
4. **Source Indicator**: See whether answer came from private KB, web search, etc.
5. **Document Upload**: Add new company documents using the admin key
6. **Responsive Design**: Works on desktop and mobile devices

### Example Questions to Try:
- "How do I connect to the company VPN from home?"
- "What is our password reset policy?"
- "What is the latest Microsoft Teams outage guidance?"
- "Hello!" (should trigger direct response)
- "Can IT support ask me to share my MFA code?"

## Debugging Common Issues

### 1. API Key/Authentication Errors
**Symptoms**: 401/403 errors, "API key missing" or "invalid key" messages
**Solutions**:
- Verify your `.env` file contains valid keys
- Check that keys are not commented out or have extra spaces
- Ensure you restarted the server after changing `.env`
- Confirm you have sufficient credits/quota on each service

### 2. Pinecone Connection Issues
**Symptoms**: Connection timeouts, index creation failures
**Solutions**:
- Verify your Pinecone API key is correct
- Check your network allows outbound connections to Pinecone
- Ensure the index name and namespace are valid
- Try deleting and recreating the index if dimension mismatch occurs

### 3. Gemini API Rate Limit Errors (429)
**Symptoms**: "You have no credits remaining" or rate limit messages
**Solutions**:
- Add credits to your Gemini account at https://makersuite.google.com/app/billing
- Check your usage at https://makersuite.google.com
- Consider using a different Gemini model if available
- Implement retry logic with exponential backoff (already partially implemented)

### 4. Groq API Issues
**Symptoms**: 429 errors, timeout errors, or invalid responses
**Solutions**:
- Check your Groq API key validity
- Verify you have sufficient credits on Groq
- Check Groq service status at their status page
- The project uses Groq for primary LLM operations - if this fails, the app may not work

### 5. Tavily Search Issues
**Symptoms**: Web search fails or returns no results
**Solutions**:
- Verify Tavily API key is correct
- Check Tavily service status
- Ensure you have sufficient quota on Tavily
- The fallback mechanism will still work even if web search fails

### 6. Vector Store Dimension Mismatch
**Symptoms**: Errors about embedding dimensions not matching Pinecone index
**Solutions**:
- The code automatically handles this by deleting and recreating the index if dimensions don't match
- Ensure `EMBEDDING_MODEL` in `.env` matches what you expect
- The default embedding model is `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

## Testing the Application

### Manual Testing via API
```bash
# Health check
curl http://127.0.0.1:8080/api/health

# Chat test
curl -X POST http://127.0.0.1:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I connect to the company VPN?"}'

# Document upload test (replace with your admin key)
curl -X POST http://127.0.0.1:8080/api/ingest \
  -H "X-Admin-Key: change-me" \
  -F "file=@path/to/your/document.pdf"
```

### Automated Testing
The project includes a basic test in `tests/test_ingestion.py`. To run tests:
```bash
pip install pytest
pytest tests/
```

#### Running Without API Keys (Local Mode Only):
To test the application with just the local embedding model (no API keys required):
```bash
python ingest_sample_kb.py  # Will use HuggingFace locally, may fail on Pinecone connection
```

You can also verify the FastAPI startup and static file serving:
```bash
python -c "from app.main import app; print('App loads successfully')"
python -c "from app.rag.vectorstore import get_embedding_dimension; print(f'Embedding dimension: {get_embedding_dimension()}')"
```

## Docker Deployment

### Building the Image
```bash
docker build -t enterprise-it-support-copilot .
```

### Running the Container
```bash
docker run -d \
  -p 8080:8080 \
  --env-file .env \
  --name enterprise-it-copilot \
  enterprise-it-support-copilot
```

### Environment Variables in Docker
Make sure your `.env` file contains all required variables when using Docker:
```env
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
TAVILY_API_KEY=your_key
PINECONE_API_KEY=your_key
PINECONE_INDEX_NAME=fde-it-support-rag
PINECONE_NAMESPACE=company-it-kb
GROQ_MODEL=openai/gpt-oss-20b
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ADMIN_API_KEY=your_secure_key
APP_ENV=production
```

## Project Structure Overview

### Core Components:
- **`app/main.py`**: FastAPI application setup
- **`app/core/config.py`**: Environment configuration management
- **`app/core/logging.py`**: Logging configuration
- **`app/api/routes.py`**: API endpoints (chat, health, ingestion)
- **`app/rag/state.py`**: LangGraph state definition
- **`app/rag/vectorstore.py`**: Pinecone vector store operations
- **`app/rag/workflow.py`**: Agentic RAG workflow (LangGraph)
- **`app/services/ingestion.py`**: Document loading and chunking
- **`app/services/audit.py`**: SQLite audit logging

### Frontend:
- **`templates/index.html`**: Main UI template
- **`static/css/style.css`**: Styling
- **`static/js/app.js`**: Client-side logic for chat and document upload

### Data:
- **`data/sample_kb/`**: Sample IT documents for initial indexing
- **`uploads/`**: Directory for uploaded documents
- **`data/audit.db`**: SQLite database for audit logs

## Troubleshooting Tips

### 1. Server Won't Start
- Check Python version (3.11+ required)
- Verify all dependencies installed: `pip list`
- Check for port conflicts (default is 8080)
- Review error logs in console output

### 2. Empty or Strange Responses
- Check the agent trace in the UI or API response
- Verify documents are properly indexed: check Pinecone console
- Test with simple questions first
- Ensure API keys are valid and have sufficient quota

### 3. UI Not Loading Properly
- Check browser console for JavaScript errors
- Verify static files are being served (check network tab)
- Ensure you're accessing the correct URL and port
- Try hard refresh (Ctrl+F5) to clear cache

### 4. Document Upload Not Working
- Verify admin key matches `ADMIN_API_KEY` in `.env`
- Check file type is supported (.pdf, .txt, .md, .docx)
- Ensure uploads directory is writable
- Check Pinecone connection and index status

## Performance Considerations

### 1. Latency Optimization
- The workflow makes multiple LLM calls (route, grade, generate) - each adds latency
- Consider adjusting `max_retries` in config for faster responses
- Pinecone queries are typically fast (<100ms)
- Web search adds significant latency (2-5 seconds typical)

### 2. Cost Management
- Monitor OpenAI usage for embeddings and LLM fallback
- Track Groq usage for primary LLM operations
- Watch Tavily API calls for search costs
- Pinecone costs depend on storage and query volume

### 3. Scaling
- For production, consider using a process manager like Gunicorn with Uvicorn workers
- Pinecone scales automatically
- Consider caching frequent queries
- Monitor audit database size and prune as needed

## Security Considerations

### 1. API Key Protection
- Never commit `.env` to version control (already in `.gitignore`)
- Use secrets management in production (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate keys periodically
- Restrict API key permissions to minimum required

### 2. Admin Endpoint Protection
- The `/api/ingest` endpoint is protected by `X-Admin-Key` header
- Change `ADMIN_API_KEY` from default in production
- Consider implementing rate limiting on admin endpoints
- Log all admin access attempts

### 3. Data Privacy
- Ensure Pinecone instance is in approved region
- Consider enabling encryption at rest for Pinecone
- Audit logs contain questions and sources - ensure proper access controls
- PII in documents should be handled according to company policy

## Maintenance

### 1. Updating Dependencies
```bash
pip list --outdated
pip install -U -r requirements.txt
```

### 2. Backing Up Data
- Pinecone vectors: Use Pinecone snapshots or export/import
- Audit logs: Backup the `data/audit.db` SQLite file
- Configuration: Backup your `.env` file (securely)
- Custom documents: Backup the `uploads/` directory

### 3. Monitoring
- Check application logs regularly
- Monitor API usage and costs
- Check Pinecone index statistics
- Monitor audit log growth
- Set up alerts for error rates or latency increases

## References and Further Reading

1. **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
2. **FastAPI Tutorial**: https://fastapi.tiangolo.com/tutorial/
3. **Pinecone Vector Database**: https://docs.pinecone.io/
4. **Groq Cloud**: https://groq.com/
5. **Tavily Search API**: https://tavily.com/
6. **OpenAI Platform**: https://platform.openai.com/docs

## Getting Help

If you encounter issues:
1. Check the console output for error messages
2. Verify all prerequisites are met
3. Confirm API keys are valid and have sufficient quota
4. Review the troubleshooting section above
5. Check the existing GitHub issues if this is from a repository
6. Consider reaching out to the project maintainers

---

**Last Updated**: 2026-10-13
**Project Version**: 1.0.0
