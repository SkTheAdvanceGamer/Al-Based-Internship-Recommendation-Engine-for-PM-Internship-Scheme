from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pdfplumber
import re
import json
import os
import random
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
PM_PORTAL_URL = "https://pminternship.mca.gov.in/"
LANG_MAP = {"hi": "Hindi", "te": "Telugu", "en": "English"}
load_dotenv(".env.txt")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        _test_client = genai.Client(api_key=GEMINI_API_KEY)
        _test_client.models.generate_content(model='gemini-2.5-flash', contents='test')
        print("[STARTUP] Gemini API key is VALID.")
    except Exception as e:
        print(f"[STARTUP] WARNING: Gemini API key FAILED: {e}")
        print("[STARTUP] Get a new key at https://aistudio.google.com/apikey")
else:
    print("[STARTUP] WARNING: No GEMINI_API_KEY found in .env.txt")
app = FastAPI(title="PM Internship Recommendation API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ManualProfile(BaseModel):
    education: str
    location: str
    preferred_sector: str
    manual_skills: List[str]
class TranslationRequest(BaseModel):
    target_language: str
    payload: Dict[str, Any]
class AgentMessage(BaseModel):
    role: str
    content: str
class AgentChatRequest(BaseModel):
    messages: List[AgentMessage]
    user_skills: List[str]
    target_language: str
class InterviewPrepRequest(BaseModel):
    job_title: str
    company: str
    skills: List[str]
class LearningRecommendationRequest(BaseModel):
    company: str
    skills: List[str]
class DynamicJobsRequest(BaseModel):
    skills: List[str]
    location: str
    education: str
    preferred_sector: str
    target_language: str
    lang: Optional[str] = "en"

# ── OmniDimension Voice AI webhook payload ────────────────────
class VoiceRecommendRequest(BaseModel):
    """Payload from OmniDimension Voice AI.
    All fields are optional — the user may not mention every detail.
    `skills` can be a single comma-separated string or a list."""
    location: Optional[str] = None
    sector: Optional[str] = None
    skills: Optional[Any] = None        # string "python, excel" OR list
    education: Optional[str] = None
    lang: Optional[str] = "en"
class ResumeSkillsResponse(BaseModel):
    skills: List[str]
class QuizQuestionDraft(BaseModel):
    question: str
    correct_answer: str
    distractors: List[str]
class QuizQuestionsResponse(BaseModel):
    questions: List[QuizQuestionDraft]
TARGET_SKILLS = {
    "Digital_Basics": ["data entry", "typing", "ms office", "excel", "word", "internet", "email"],
    "Vocational": ["agriculture", "wiring", "hardware", "plumbing", "mechanic", "welding", "carpentry", "solar"],
    "Logistics_Retail": ["inventory", "dispatch", "customer service", "packaging", "supply chain"],
    "Core_IT": ["python", "c++", "c", "java", "sql", "html", "networking", "troubleshooting"],
    "Healthcare_Basics": ["first aid", "sanitation", "patient care", "health records"]
}
def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
def _dedupe_preserve(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
def _strip_code_fences(text: str) -> str:
    return (text or "").replace("```json", "").replace("```", "").strip()
def _normalize_language(target_language: str) -> str:
    lowered = _clean_text(target_language).casefold()
    if lowered in {"hi", "hindi", "हिंदी"}:
        return "hi"
    if lowered in {"te", "telugu", "తెలుగు"}:
        return "te"
    return "en"
def _extract_pdf_text(file_bytes: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            text = "\n".join([(page.extract_text() or "") for page in pdf.pages])
    except Exception as e:
        print(f"PDF Parsing Warning: {e}")
    if len(_clean_text(text)) >= 250:
        return text
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=3)
        ocr_text = "\n".join([
            pytesseract.image_to_string(image) for image in images
        ])
        if len(_clean_text(ocr_text)) > len(_clean_text(text)):
            return ocr_text
    except Exception as e:
        print(f"OCR Fallback Warning: {e}")
    return text
def _call_gemini_structured(prompt: str, schema_model: type[BaseModel], api_key: str, *, system_instruction: Optional[str] = None, temperature: float = 0.2, max_output_tokens: int = 2048) -> BaseModel:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema_model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    parsed = response.parsed
    if isinstance(parsed, schema_model):
        return parsed
    if isinstance(parsed, dict):
        return schema_model.model_validate(parsed)
    raise RuntimeError("Gemini returned an unexpected structured response")
def _normalize_skills(skills: List[str]) -> List[str]:
    cleaned = []
    for skill in skills:
        normalized = _clean_text(skill)
        if normalized:
            cleaned.append(normalized)
    return _dedupe_preserve(cleaned)
def _build_quiz_question(question: QuizQuestionDraft) -> Dict[str, Any]:
    prompt = _clean_text(question.question)
    correct_answer = _clean_text(question.correct_answer)
    distractors = _normalize_skills(question.distractors)
    distractors = [item for item in distractors if item.casefold() != correct_answer.casefold()]
    if not prompt or not correct_answer or len(distractors) < 3:
        raise ValueError("Gemini returned an incomplete quiz question")
    options = [correct_answer, distractors[0], distractors[1], distractors[2]]
    if len(_dedupe_preserve(options)) < 4:
        raise ValueError("Gemini returned duplicate quiz options")
    random.SystemRandom().shuffle(options)
    return {
        "q": prompt,
        "options": options,
        "a": next(option for option in options if option.casefold() == correct_answer.casefold()),
    }
def extract_skills_with_gemini(text: str, api_key: str) -> List[str]:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    resume_text = _clean_text(text)
    if not resume_text:
        raise RuntimeError("Could not extract readable text from the PDF")
    try:
        response = _call_gemini_structured(
            prompt=(
                "Extract the 5 to 8 strongest resume-evidenced skills from the text below.\n"
                "Rules:\n"
                "- Prefer concrete skills, tools, technologies, platforms, methods, and domain abilities.\n"
                "- Do not include generic soft skills like communication, leadership, or hardworking unless the resume has no stronger skill evidence.\n"
                "- Use the exact skill names from the resume where possible.\n"
                "- Return only skills that are clearly supported by the resume text.\n\n"
                f"RESUME TEXT:\n{resume_text[:12000]}"
            ),
            schema_model=ResumeSkillsResponse,
            api_key=api_key,
            system_instruction="You extract only resume-supported skills and return strict JSON.",
            temperature=0.1,
            max_output_tokens=512,
        )
        skills = _normalize_skills(response.skills)
        if not skills:
            raise RuntimeError("Gemini returned no usable skills")
        return skills[:8]
    except Exception as e:
        print(f"LLM Extraction Error: {e}")
        raise RuntimeError("Skill extraction failed") from e
def generate_dynamic_questions(skills: List[str], api_key: str, num_questions=3):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")
    normalized_skills = _normalize_skills(skills)
    if not normalized_skills:
        raise RuntimeError("No skills available for question generation")
    last_error: Optional[Exception] = None
    for _ in range(2):
        try:
            response = _call_gemini_structured(
                prompt=(
                    f"Create exactly {num_questions} multiple-choice interview questions based only on these skills: {', '.join(normalized_skills)}.\n"
                    "Rules:\n"
                    "- Every question must directly test one of the provided skills.\n"
                    "- Do not ask about skills that are not in the list.\n"
                    "- Make the questions realistic and interview-ready, not generic aptitude questions.\n"
                    "- For each question, provide one correct answer and exactly three plausible wrong answers.\n"
                    "- Keep each option short and distinct.\n"
                    "- Avoid 'all of the above' and 'none of the above'."
                ),
                schema_model=QuizQuestionsResponse,
                api_key=api_key,
                system_instruction="You create precise interview MCQs and return strict JSON.",
                temperature=0.35,
                max_output_tokens=2048,
            )
            questions: List[Dict[str, Any]] = []
            seen_prompts = set()
            for item in response.questions:
                built_question = _build_quiz_question(item)
                prompt_key = built_question["q"].casefold()
                if prompt_key in seen_prompts:
                    continue
                seen_prompts.add(prompt_key)
                questions.append(built_question)
            if len(questions) >= num_questions:
                return questions[:num_questions]
            raise RuntimeError(f"Gemini returned only {len(questions)} valid questions")
        except Exception as e:
            print(f"[ERROR] generate_dynamic_questions failed: {e}")
            last_error = e
    raise RuntimeError("Question generation failed") from last_error
def rag_semantic_search(user_profile: dict, user_skills: List[str], top_n=5):
    """TF-IDF based semantic search. Strictly returns top 3-5 results."""
    top_n = max(3, min(top_n, 5))
    try:
        with open("jobs.json", "r", encoding="utf-8") as f:
            db_jobs = json.load(f)
    except Exception as e:
        print(f"Error loading jobs.json: {e}")
        return []
    if not db_jobs:
        return []
    corpus = [f"{j.get('sector','')} {j.get('location','')} {j.get('title','')} {' '.join(j.get('skills',[]))} {j.get('description','')}" for j in db_jobs]
    query = f"{user_profile.get('preferred_sector', '')} {user_profile.get('location', '')} {user_profile.get('education', '')} {' '.join(user_skills)}"
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(corpus + [query])
    cosine_similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    ranked = []
    for idx, score in enumerate(cosine_similarities):
        intern_data = db_jobs[idx].copy()
        intern_data['match_score'] = min(int(score * 100) + 15, 99)
        ranked.append(intern_data)
    ranked.sort(key=lambda x: x['match_score'], reverse=True)
    return ranked[:top_n]
def translate_text_lightweight(text: str, dest_lang: str) -> str:
    """Translate text using Gemini. Falls back to original on error."""
    if not text or dest_lang == "en":
        return text
    if not GEMINI_API_KEY:
        return text
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        lang_name = LANG_MAP.get(dest_lang, dest_lang)
        prompt = f"Translate the following text to {lang_name}. Return ONLY the translated text, nothing else.\n\nText: {text}"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Translation error: {e}")
    return text
def generate_interview_prep(job_title: str, company: str, skills: List[str], api_key: str):
    fallback = [{"q": "Why do you want to work at " + company + "?", "options": ["Growth opportunity", "Good culture", "Skill development", "Location preference"], "a": "Growth opportunity"},
               {"q": "What is your greatest strength?", "options": ["Problem solving", "Teamwork", "Time management", "Creativity"], "a": "Problem solving"},
               {"q": "How do you handle deadlines?", "options": ["Plan ahead", "Work overtime", "Ask for extensions", "Ignore them"], "a": "Plan ahead"}]
    if not api_key:
        return fallback
    try:
        client = genai.Client(api_key=api_key)
        skills_str = ', '.join(skills) if skills else "general skills"
        prompt = (
            "You are an expert technical interviewer at " + company + " interviewing a candidate for the '" + job_title + "' role.\n"
            "The candidate has the following skills: " + skills_str + ".\n"
            "Generate 5 UNIQUE, company-specific and role-specific multiple-choice interview questions.\n"
            'Return ONLY a valid JSON array of objects. Format: [{"q": "Question?", "options": ["A", "B", "C", "D"], "a": "Correct answer"}]'
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        clean_json = _strip_code_fences(response.text)
        parsed = json.loads(clean_json)
        return parsed if parsed else fallback
    except Exception as e:
        print(f"[ERROR] generate_interview_prep failed: {e}")
        return fallback
def fetch_learning_recommendations(company: str, skills: List[str], api_key: str):
    fallback = [{"title": "Two Sum", "difficulty": "Easy", "acceptance": "50%", "topic": "Arrays"},
                {"title": "Valid Parentheses", "difficulty": "Easy", "acceptance": "42%", "topic": "Stacks"},
                {"title": "Reverse Linked List", "difficulty": "Easy", "acceptance": "73%", "topic": "Linked Lists"}]
    if not api_key:
        return fallback
    try:
        client = genai.Client(api_key=api_key)
        skills_str = ', '.join(skills) if skills else "general skills"
        prompt = (
            "You are a career advisor. Based on the target company '" + company + "' and the candidate's skills: " + skills_str + ",\n"
            "recommend 6 specific 'Leetcode-style' coding problems or core technical concepts they should master to pass the interview at " + company + ".\n"
            'Return ONLY a valid JSON array of objects. Format: [{"title": "Problem Title", "difficulty": "Easy/Medium/Hard", "acceptance": "Percentage", "topic": "Core Topic"}]'
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        clean_json = _strip_code_fences(response.text)
        parsed = json.loads(clean_json)
        return parsed if parsed else fallback
    except Exception as e:
        print(f"[ERROR] fetch_learning_recommendations failed: {e}")
        return fallback
@app.get("/")
def health_check():
    return {"status": "Engine is running smoothly."}
@app.post("/analyze-resume")
async def analyze_resume(file: UploadFile = File(...), location: str = "Amaravati", education: str = "Graduate", preferred_sector: str = "Any"):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    try:
        file_bytes = await file.read()
        text = _extract_pdf_text(file_bytes)
        extracted_skills = extract_skills_with_gemini(text, GEMINI_API_KEY)
        quiz = generate_dynamic_questions(extracted_skills, GEMINI_API_KEY, num_questions=5)
        return {
            "extracted_skills": extracted_skills,
            "assessment_quiz": quiz,
            "profile_dict": {"location": location, "education": education, "preferred_sector": preferred_sector}
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")
@app.post("/manual-profile")
def process_manual_profile(profile: ManualProfile):
    try:
        normalized_skills = _normalize_skills(profile.manual_skills)
        quiz = generate_dynamic_questions(normalized_skills, GEMINI_API_KEY, num_questions=5)
        profile_dict = {
            "location": profile.location,
            "education": profile.education,
            "preferred_sector": profile.preferred_sector
        }
        return {
            "status": "Profile registered successfully",
            "verified_skills": normalized_skills,
            "assessment_quiz": quiz,
            "profile_dict": profile_dict
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
@app.post("/recommended-jobs")
def get_recommended_jobs(request: DynamicJobsRequest):
    profile_dict = {
        "location": request.location,
        "education": request.education,
        "preferred_sector": request.preferred_sector
    }
    jobs = rag_semantic_search(profile_dict, request.skills, top_n=5)
    lang = getattr(request, 'lang', 'en') or 'en'
    if lang in ('hi', 'te'):
        for job in jobs:
            job['title'] = translate_text_lightweight(job.get('title', ''), lang)
            job['sector'] = translate_text_lightweight(job.get('sector', ''), lang)
    return {"top_matches": jobs}

# ── OmniDimension Voice AI Webhook ────────────────────────────
@app.post("/api/voice-recommend")
def voice_recommend(request: VoiceRecommendRequest):
    """
    Endpoint for OmniDimension Voice AI webhook.
    Accepts a flexible JSON payload with optional fields.
    Returns a CLEAN, flat JSON with only the top 3-5 internships.
    
    OmniDimension Dashboard Mapping:
      - location  → user's spoken city/state
      - sector    → user's spoken industry preference
      - skills    → extracted skill keywords (string or list)
      - education → qualification level mentioned
      - lang      → response language (en/hi/te)
    """
    # Normalize skills: accept both "python, excel" string and ["python","excel"] list
    user_skills = []
    if request.skills:
        if isinstance(request.skills, list):
            user_skills = [s.strip() for s in request.skills if s.strip()]
        elif isinstance(request.skills, str):
            user_skills = [s.strip() for s in request.skills.split(",") if s.strip()]
    if not user_skills:
        user_skills = ["communication", "general skills"]

    profile_dict = {
        "location": request.location or "",
        "education": request.education or "Graduate",
        "preferred_sector": request.sector or "Any",
    }

    jobs = rag_semantic_search(profile_dict, user_skills, top_n=5)
    lang = request.lang or "en"

    # Translate if needed
    if lang in ("hi", "te"):
        for job in jobs:
            job["title"] = translate_text_lightweight(job.get("title", ""), lang)
            job["sector"] = translate_text_lightweight(job.get("sector", ""), lang)

    # Return a CLEAN response — only what the voice AI needs to read back
    clean_results = []
    for job in jobs:
        clean_results.append({
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "sector": job.get("sector", ""),
            "match_score": job.get("match_score", 0),
            "apply_url": job.get("apply_url", PM_PORTAL_URL),
        })

    return {
        "count": len(clean_results),
        "internships": clean_results,
    }
class JobTipRequest(BaseModel):
    title: str
    company: str
    language: str
@app.post("/job-tips")
def get_job_tips(request: JobTipRequest):
    if not GEMINI_API_KEY:
        return {"tips": ["Be confident", "Arrive on time", "Research the company"]}
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        Provide exactly 3 short, actionable interview or application tips for the '{request.title}' role at '{request.company}'.
        Translate the tips into {request.language}.
        Return ONLY a JSON array of 3 strings.
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        clean_json = _strip_code_fences(response.text)
        return {"tips": json.loads(clean_json)}
    except Exception:
        return {"tips": ["Prepare thoroughly", "Communicate clearly", "Review your resume"]}
@app.post("/translate")
def translate_content(request: TranslationRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="API Key missing")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        You are an expert localization engine designing interfaces for first-generation digital learners in India.
        Translate the following JSON UI text and job descriptions into {request.target_language}.
        RULES:
        1. Use simple, everyday colloquial vocabulary. Avoid highly formalized or academic terms.
        2. Maintain an 8th-grade reading level.
        3. If a technical term (like "API", "Python", "Data Entry") is universally understood in English, transliterate it rather than inventing a complex native translation.
        4. Return ONLY a valid JSON object with the exact same keys, but translated values.
        PAYLOAD TO TRANSLATE:
        {json.dumps(request.payload)}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        clean_json = _strip_code_fences(response.text)
        return {"translated_payload": json.loads(clean_json)}
    except Exception as e:
        print(f"Translation Error: {e}")
        return {"translated_payload": request.payload, "warning": "Translation failed, defaulting to English."}
@app.post("/agent-chat")
def agent_chat(request: AgentChatRequest):
    if not GEMINI_API_KEY:
        return {"reply": "AI mentor is unavailable because GEMINI_API_KEY is missing."}
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        preferred_language = LANG_MAP.get(_normalize_language(request.target_language), request.target_language)
        system_instruction = f"""
        You are a highly empathetic, encouraging Career Mentor for rural Indian youth applying to the PM Internship Scheme.
        The user has these verified skills: {', '.join(request.user_skills)}.
        Their preferred language for responses is: {preferred_language}. You MUST reply ONLY in this language. Use simple, colloquial, 8th-grade vocabulary.
        YOUR ROLE:
        1. Acknowledge their skills and build confidence.
        2. Give them 1 specific, practical interview tip based on their skills.
        3. Suggest 1 free learning step to improve.
        4. Keep responses extremely short (max 3-4 sentences). Do not use emojis.
        """
        conversation_context = "Conversation History:\n"
        for msg in request.messages[:-1]:
            role_name = "User" if msg.role == "user" else "Mentor"
            conversation_context += f"{role_name}: {msg.content}\n"
        current_msg = request.messages[-1].content if request.messages else "Hello!"
        final_prompt = f"{system_instruction}\n\n{conversation_context}\nUser: {current_msg}\nMentor:"
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=final_prompt,
        )
        return {"reply": response.text.strip()}
    except Exception as e:
        print(f"[ERROR] agent-chat failed: {e}")
        return {"reply": "AI mentor is temporarily unavailable. Please try again."}
@app.post("/interview-prep")
def interview_prep_endpoint(request: InterviewPrepRequest):
    questions = generate_interview_prep(request.job_title, request.company, request.skills, GEMINI_API_KEY)
    return {"questions": questions}
@app.post("/learning-recommendations")
def learning_recommendations_endpoint(request: LearningRecommendationRequest):
    recommendations = fetch_learning_recommendations(request.company, request.skills, GEMINI_API_KEY)
    return {"recommendations": recommendations}
