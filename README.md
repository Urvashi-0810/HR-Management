

Now let me create the comprehensive project documentation:

Created project_overview.md

The complete Part 1 backend is built and verified. Here's what you have:

### 4 Pipeline Steps — each works independently or in sequence

| Step | Module | What it does |
|------|--------|-------------|
| **1. Download** | [`email_downloader.py`](file:///d:/Projects/HR-Management-System-2/src/email_downloader.py) | IMAP email scanner → downloads CV attachments → tracks progress in JSON |
| **2. Extract** | [`llm_extractor.py`](file:///d:/Projects/HR-Management-System-2/src/llm_extractor.py) | Reads PDFs/DOCX/images → sends text to Claude/Gemini → structured JSON → Excel |
| **3. Shortlist** | [`shortlister.py`](file:///d:/Projects/HR-Management-System-2/src/shortlister.py) | Filters by experience, age, skills, education, location → shortlisted Excel |
| **4. Job Match** | [`job_matcher.py`](file:///d:/Projects/HR-Management-System-2/src/job_matcher.py) | Sends each shortlisted CV + JD to LLM → scores (0-100), strengths, weaknesses |

### Two ways to use it

1. **CLI** — `.\venv\Scripts\python.exe -m src.pipeline extract` (or `download`, `shortlist`, `match`, `full`)
2. **API Server** — `.\venv\Scripts\python.exe run.py` → 12 REST endpoints at `http://localhost:8000/docs`

### To get started right now

1. Edit [`.env`](file:///d:/Projects/HR-Management-System-2/.env) — add your **Gemini or Claude API key** (and email credentials if you want Step 1)
2. Drop some CVs into [`cvs/`](file:///d:/Projects/HR-Management-System-2/cvs) (or run `download` to pull from email)
3. Run: `.\venv\Scripts\python.exe -m src.pipeline extract`

See the full documentation artifact above for all details. Ready to build the React frontend when you are!
