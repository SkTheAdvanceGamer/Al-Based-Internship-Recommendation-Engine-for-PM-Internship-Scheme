<div align="center">

# AI-Based Internship Recommendation Engine
### PM Internship Scheme | Intelligent Candidate-to-Opportunity Matching

[![License: MIT](https://img.shields.io/badge/License-MIT-2563eb.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-0ea5e9?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-22c55e?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-06b6d4?logo=react&logoColor=white)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8-f59e0b?logo=vite&logoColor=white)](https://vitejs.dev)

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,50:1d4ed8,100:0ea5e9&height=140&section=header&text=Trust%20Score%20Driven%20Internship%20Intelligence&fontSize=28&fontColor=ffffff&animation=fadeIn" alt="Header banner" />

**A voice-first, multilingual, trust-aware platform that helps candidates discover the right internships and helps programs evaluate readiness with transparency.**

</div>

---

## Project Vision
This project is built to support high-scale internship programs where discoverability, fairness, and readiness evaluation matter as much as raw application volume.

It combines:
- Intelligent candidate profiling
- Structured skill assessment
- Trust score signals
- Explainable job matching
- Voice-led interview workflows

The result is a guided pathway from profile creation to final opportunity shortlist.

---

## Core Experience (End-to-End Flow)
1. Candidate creates profile and uploads resume.
2. System extracts structured details (skills, education, contacts, project cues).
3. Candidate completes multi-stage assessment:
   - Test 1: Basics
   - Test 2: Deep + coding
   - Test 3: Agentic voice interview
4. Platform computes trust and readiness signals.
5. Matching engine ranks internships by relevance and confidence.
6. Candidate gets a polished results dashboard with explainable scoring.

---

## Feature Highlights

### 1) Resume Intelligence
- PDF and scanned resume support
- OCR pipeline for image-based content
- Skill/entity extraction with robust fallbacks
- Contact and profile signal extraction
- ATS-style quality guidance

### 2) Dynamic Assessment Engine
- Progressive 3-test structure
- Coding editor and execution support
- Anti-cheating telemetry (tab switching, copy/paste, timing checks)
- Score capping logic for skipped optional stages

### 3) Voice-First Interview Stage (Test 3)
- Candidate-specific voice interview session start
- Domain-aware interview setup
- Status polling and completion tracking
- Post-interview transcript and evaluation storage
- Result page rendering for final review

### 4) Trust Score Framework
- Multi-factor scoring architecture
- Weighted contribution from assessment, profile quality, and verification signals
- Designed for explainability and auditability

### 5) Smart Matching
- Skill-to-role similarity scoring
- Domain and location compatibility checks
- Ranked output with confidence and rationale

### 6) Accessibility and Reach
- Multilingual-first design
- Mobile-ready frontend
- Supportive UI for first-time internet users

---

## System Architecture

```text
Frontend (Web + Mobile)
  -> Onboarding + Assessment + Dashboard + Voice UI
  -> REST APIs

Backend (FastAPI)
  -> Resume Parsing
  -> Assessment Orchestration
  -> Trust Score Engine
  -> Matching Engine
  -> Interview Session APIs + Webhook Handlers

Services and Tooling
  -> OCR, translation, code execution, scraping, auth, and storage integrations
```

---

## Technology Stack

### Backend
- FastAPI
- Pydantic
- OCR and document parsing utilities
- Scikit-learn (similarity and ranking support)
- Async HTTP integrations and webhook handling

### Frontend
- React + Vite
- Component-driven onboarding and assessment screens
- Rich result dashboards
- Responsive layouts for desktop and mobile

### DevOps
- Docker and docker-compose support
- Environment-based configuration

---

## API Surface (High-Level)

### Candidate + Assessment APIs
- Profile, parsing, and readiness endpoints
- Stage-wise assessment computation and submission

### Voice Interview APIs
- `POST /api/interview/start`
- `POST /api/interview/webhook`
- `GET /api/interview/result/{candidate_id}`
- `GET /interview/result?id={candidate_id}`

### Dashboard APIs
- Final score aggregation
- Match output and recommendation payloads

---

## Project Structure

```text
.
├── main.py
├── interview_agent.py
├── interview_api.py
├── templates/
│   ├── interview.html
│   └── result.html
├── frontend/
│   └── src/
│       └── components/
│           └── onboarding/
├── mobile-app/
├── requirements.txt
└── docker-compose.yml
```

---

## Quick Start

### 1) Clone
```bash
git clone https://github.com/SkTheAdvanceGamer/Al-Based-Internship-Recommendation-Engine-for-PM-Internship-Scheme.git
cd Al-Based-Internship-Recommendation-Engine-for-PM-Internship-Scheme
```

### 2) Backend
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3) Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4) Mobile App (optional)
```bash
cd mobile-app
npm install
npm run dev
```

---

## Configuration
Create your local env file from template and fill required keys:

```bash
cp .env.example .env.txt
```

This repository already ignores secrets-oriented files (like `.env`, `.env.txt`, and `.env.local`) in `.gitignore`.

---

## Current Status
- Multi-stage assessment flow integrated
- Voice interview workflow integrated into onboarding journey
- Interview result rendering available
- End-to-end matching and scoring pipeline active

---

## Roadmap
- Persistence layer hardening for interview sessions
- Advanced analytics for interviewer quality and candidate growth trends
- Deeper explainability panels for match outcomes
- Enterprise-grade admin controls and review tooling

---

## Contributing
Contributions are welcome. Please open an issue first for major feature proposals, then submit a focused PR with clear context and test notes.

---

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE).

