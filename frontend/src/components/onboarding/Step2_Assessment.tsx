import { useEffect, useMemo, useState } from "react";
import { Brain, CheckCircle2, Code2, ExternalLink, Loader2, Mic, RefreshCw, Play } from "lucide-react";
import { generateAssessmentBundle, executeCode, calculateCheatingScore } from "./onboardingApi";
import { MonacoCodeEditor } from "./MonacoCodeEditor";
import { CheatingDetector } from "./CheatingDetector";
import type { AssessmentBundle, StageScores, StageTab } from "./types";

const VOICE_DOMAIN_OPTIONS = [
  "Banking and Finance",
  "Automobile",
  "FMCG",
  "Telecom",
  "Healthcare",
  "IT Services",
  "Oil and Gas",
  "Tourism and Hospitality",
  "Railways",
  "Renewable Energy",
];
const DEPLOYED_OMNIDIM_WIDGET_SECRET = "4eaec02415cd7727a99f83d1bf2aba3f";

const apiBaseCandidates = Array.from(
  new Set(
    [import.meta.env.VITE_API_BASE_URL, "http://localhost:8000", "http://localhost:8001"].filter(Boolean),
  ),
);

function safeUUID() {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // ignore
  }

  const hex = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1);
  return `${hex()}${hex()}-${hex()}-${hex()}-${hex()}-${hex()}${hex()}${hex()}`;
}

function parseConfidenceScore(text: unknown): number | null {
  const raw = String(text || "").trim();
  if (!raw) return null;

  const normalized = raw.replace(/\s+/g, " ");
  const explicit = normalized.match(/(\d+(?:\.\d+)?)\s*(?:\/\s*10\b|\/10\b|out of\s*10\b)/i);
  if (explicit && explicit[1]) {
    const score = Number(explicit[1]);
    if (Number.isFinite(score)) return Math.max(1, Math.min(10, score));
  }

  const fallback = normalized.match(/\b(10|[1-9])\b/);
  if (fallback && fallback[1]) {
    const score = Number(fallback[1]);
    if (Number.isFinite(score)) return Math.max(1, Math.min(10, score));
  }

  return null;
}

function normalizeRating(value: string) {
  const cleaned = value.trim().toLowerCase();
  if (cleaned.includes("excellent")) return "Excellent" as const;
  if (cleaned.includes("good")) return "Good" as const;
  if (cleaned.includes("average")) return "Average" as const;
  if (cleaned.includes("poor")) return "Poor" as const;
  return null;
}

function parseAnswerQuality(value: unknown): Array<"Excellent" | "Good" | "Average" | "Poor"> {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeRating(String(item || "")))
      .filter(Boolean) as Array<"Excellent" | "Good" | "Average" | "Poor">;
  }

  const text = String(value || "");
  const results: Array<"Excellent" | "Good" | "Average" | "Poor"> = [];

  const labeled = /Q\s*([1-5])\s*[:\-]\s*(Excellent|Good|Average|Poor)/gi;
  let match: RegExpExecArray | null = null;
  while ((match = labeled.exec(text))) {
    const idx = Number(match[1]) - 1;
    const rating = normalizeRating(match[2]);
    if (idx >= 0 && idx < 5 && rating) results[idx] = rating;
  }

  if (results.filter(Boolean).length) {
    return Array.from({ length: 5 }, (_, i) => results[i] || "Average");
  }

  const words = text.match(/Excellent|Good|Average|Poor/gi) || [];
  return words
    .slice(0, 5)
    .map((w) => normalizeRating(w))
    .filter(Boolean) as Array<"Excellent" | "Good" | "Average" | "Poor">;
}

function calculateVoiceStageScore(session: Record<string, any> | null): number {
  if (!session || session.status !== "completed") return 0;

  const evaluation = (session.evaluation || {}) as Record<string, any>;
  const confidence = parseConfidenceScore(evaluation.confidence_score_text);
  const confidencePoints = confidence === null ? null : confidence * 10;

  const quality = parseAnswerQuality(evaluation.answer_quality);
  const ratingPoints: Record<string, number> = {
    Excellent: 100,
    Good: 85,
    Average: 65,
    Poor: 45,
  };
  const qualityPoints = quality.length
    ? Math.round(quality.reduce((sum, item) => sum + (ratingPoints[item] ?? 60), 0) / quality.length)
    : null;

  if (confidencePoints === null && qualityPoints === null) return 65;
  if (confidencePoints === null) return qualityPoints ?? 65;
  if (qualityPoints === null) return confidencePoints;
  return Math.round(confidencePoints * 0.5 + qualityPoints * 0.5);
}

type Step2AssessmentProps = {
  skills: string[];
  onBack: () => void;
  onComplete: (scores: StageScores) => void;
};

export function Step2_Assessment({ skills, onBack, onComplete }: Step2AssessmentProps) {
  const [activeTab, setActiveTab] = useState<StageTab>("basics");
  const [bundle, setBundle] = useState<AssessmentBundle | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [codeByChallenge, setCodeByChallenge] = useState<Record<string, string>>({});
  const [executionResults, setExecutionResults] = useState<Record<string, { stdout: string; stderr: string; error: boolean }>>({});
  const [loading, setLoading] = useState(true);
  const [isTest2Skipped, setIsTest2Skipped] = useState(false);
  const [isVoiceSkipped, setIsVoiceSkipped] = useState(false);

  // Voice interview (Test 3)
  const [voiceCandidateName, setVoiceCandidateName] = useState("");
  const [voiceDomain, setVoiceDomain] = useState(VOICE_DOMAIN_OPTIONS[0] || "General");
  const [voiceCandidateId, setVoiceCandidateId] = useState("");
  const [voiceApiBase, setVoiceApiBase] = useState<string | null>(null);
  const [voiceSession, setVoiceSession] = useState<Record<string, any> | null>(null);
  const [voiceStage3Score, setVoiceStage3Score] = useState<number>(0);
  const [voiceLaunching, setVoiceLaunching] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("Not started");
  const [voiceWidgetVisible, setVoiceWidgetVisible] = useState(false);
  
  // Cheating Telemetry
  const [telemetry, setTelemetry] = useState({ tabSwitches: 0, copyPasteCount: 0 });
  const [startTime] = useState(Date.now());

  useEffect(() => {
    if (typeof window === "undefined") return;

    const storedId = (window.localStorage.getItem("pm_voice_candidate_id") || "").trim();
    const nextId = storedId || safeUUID();
    window.localStorage.setItem("pm_voice_candidate_id", nextId);
    setVoiceCandidateId(nextId);

    const storedName = (window.localStorage.getItem("pm_voice_candidate_name") || "").trim();
    if (storedName) setVoiceCandidateName(storedName);

    const storedDomain = (window.localStorage.getItem("pm_voice_domain") || "").trim();
    if (storedDomain) setVoiceDomain(storedDomain);
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    generateAssessmentBundle(skills).then((nextBundle) => {
      if (!alive) return;
      setBundle(nextBundle);
      setCodeByChallenge(
        Object.fromEntries(nextBundle.deep.map((challenge) => [challenge.id, challenge.starterCode])),
      );
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [skills]);

  const resolveVoiceApiBase = async (candidateId: string) => {
    for (const baseUrl of apiBaseCandidates) {
      try {
        const res = await fetch(`${baseUrl}/api/interview/result/${encodeURIComponent(candidateId)}`, { cache: "no-store" });
        if (res) return baseUrl;
      } catch {
        // try next base URL
      }
    }
    return null;
  };

  const startVoiceInterviewSession = async (
    candidateName: string,
    domain: string,
    candidateId: string,
  ): Promise<{ baseUrl: string; payload: Record<string, any> }> => {
    let lastError: string | null = null;

    for (const baseUrl of apiBaseCandidates) {
      try {
        const response = await fetch(`${baseUrl}/api/interview/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            candidate_name: candidateName,
            domain,
            candidate_id: candidateId,
          }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const message = String(data?.details || data?.error || `HTTP ${response.status}`);
          lastError = message;
          continue;
        }

        return { baseUrl, payload: data as Record<string, any> };
      } catch (error: any) {
        lastError = String(error?.message || "Network error");
      }
    }

    throw new Error(lastError || "Could not start voice interview session.");
  };

  const mountOmniWidgetInline = (secretKey: string) => {
    const host = document.getElementById("omni-widget-component");
    if (!host) {
      throw new Error("OmniDimension widget container was not found on the page.");
    }

    host.innerHTML = "";
    const existingScript = document.getElementById("omnidimension-web-widget");
    if (existingScript?.parentElement) {
      existingScript.parentElement.removeChild(existingScript);
    }

    const script = document.createElement("script");
    script.id = "omnidimension-web-widget";
    script.async = true;
    script.src = `https://omnidim.io/web_widget.js?secret_key=${secretKey}`;
    host.parentElement?.appendChild(script);
  };

  const pollVoiceSession = async (baseOverride?: string) => {
    const candidateId = (voiceCandidateId || "").trim();
    if (!candidateId) return;

    let baseUrl = baseOverride || voiceApiBase;
    if (!baseUrl) {
      baseUrl = await resolveVoiceApiBase(candidateId);
      if (baseUrl) setVoiceApiBase(baseUrl);
    }

    if (!baseUrl) return;

    try {
      const res = await fetch(`${baseUrl}/api/interview/result/${encodeURIComponent(candidateId)}`, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));

      if (res.status === 200 && data && data.status === "completed") {
        setVoiceSession(data);
        const stage3 = calculateVoiceStageScore(data);
        setVoiceStage3Score(stage3);
        setVoiceStatus(`Completed (Score: ${stage3}/100)`);
        return;
      }

      if (res.status === 202) {
        setVoiceStatus("Processing your voice interview...");
        return;
      }

      if (res.status === 404) {
        setVoiceStatus("Waiting for you to start/finish the voice interview...");
        return;
      }

      setVoiceStatus(`Voice interview status: ${res.status}`);
    } catch {
      setVoiceStatus("Could not reach the voice interview server.");
    }
  };

  useEffect(() => {
    if (isVoiceSkipped) return;
    if (!voiceCandidateId) return;
    if (voiceSession?.status === "completed") return;
    if (!voiceApiBase) return;

    const timer = window.setInterval(() => {
      void pollVoiceSession();
    }, 3000);

    return () => window.clearInterval(timer);
  }, [isVoiceSkipped, voiceApiBase, voiceCandidateId, voiceSession?.status]);

  const launchVoiceInterview = async () => {
    if (voiceLaunching) return;

    const name = voiceCandidateName.trim();
    const domain = voiceDomain.trim();
    const candidateId = voiceCandidateId.trim() || safeUUID();

    if (!name) {
      alert("Please enter your full name for the voice interview.");
      return;
    }
    if (!domain) {
      alert("Please select a domain for the voice interview.");
      return;
    }

    if (typeof window !== "undefined") {
      window.localStorage.setItem("pm_voice_candidate_name", name);
      window.localStorage.setItem("pm_voice_domain", domain);
      window.localStorage.setItem("pm_voice_candidate_id", candidateId);
    }

    setVoiceCandidateId(candidateId);
    setIsVoiceSkipped(false);
    setVoiceLaunching(true);
    setVoiceStatus("Opening voice interview...");

    try {
      const { baseUrl, payload } = await startVoiceInterviewSession(name, domain, candidateId);
      setVoiceApiBase(baseUrl);

      const token = String(payload?.web_call_token || "").trim();
      if (!token && !DEPLOYED_OMNIDIM_WIDGET_SECRET) {
        throw new Error("Backend did not return web_call_token for OmniDimension.");
      }

      const widgetSecret = String(
        import.meta.env.VITE_OMNIDIM_WIDGET_SECRET || DEPLOYED_OMNIDIM_WIDGET_SECRET || token,
      ).trim();
      mountOmniWidgetInline(widgetSecret);
      setVoiceWidgetVisible(true);

      setVoiceStatus("Voice interview started. OmniDimension assistant is now open below.");
      void pollVoiceSession(baseUrl);
    } catch (error: any) {
      console.error(error);
      setVoiceStatus("Failed to launch voice interview.");
      alert(error?.message || "Voice interview could not be started.");
    } finally {
      setVoiceLaunching(false);
    }
  };

  const completion = useMemo(() => {
    const voiceDone = isVoiceSkipped || voiceSession?.status === "completed";
    if (!bundle) return { basics: 0, deep: 0, voice: voiceDone ? 100 : 0 };
    const answeredBasics = bundle.basics.filter((question) => answers[question.id]?.trim()).length;
    const solvedDeep = bundle.deep.filter((challenge) => codeByChallenge[challenge.id]?.trim().length > 10).length;
    return {
      basics: Math.round((answeredBasics / Math.max(bundle.basics.length, 1)) * 100),
      deep: Math.round((solvedDeep / Math.max(bundle.deep.length, 1)) * 100),
      voice: voiceDone ? 100 : 0,
    };
  }, [answers, bundle, codeByChallenge, isVoiceSkipped, voiceSession?.status]);

  const handleRunCode = async (challengeId: string) => {
    const code = codeByChallenge[challengeId] || "";
    setExecutionResults(prev => ({ ...prev, [challengeId]: { stdout: "Executing...", stderr: "", error: false } }));
    const result = await executeCode(code, "python");
    setExecutionResults(prev => ({ ...prev, [challengeId]: result }));
  };

  const submitAssessment = async () => {
    if (!bundle) return;

    const voiceCompleted = voiceSession?.status === "completed";
    if (!isVoiceSkipped && !voiceCompleted) {
      alert("Please complete Test 3 (Voice Interview) or skip it to submit.");
      setActiveTab("voice");
      return;
    }
    
    // Calculate cheating score
    const timeTakenSeconds = Math.floor((Date.now() - startTime) / 1000);
    const cheatScore = await calculateCheatingScore({
      tabSwitches: telemetry.tabSwitches,
      copyPasteCount: telemetry.copyPasteCount,
      timeTakenSeconds
    });

    const correctBasics = bundle.basics.reduce((score, question) => {
      const userAnswer = (answers[question.id] || "").trim().toLowerCase();
      if (!userAnswer) return score;
      if (question.type === "short") return score + (userAnswer.length > 18 ? 1 : 0.5);
      return score + (userAnswer === (question.answer || "").trim().toLowerCase() ? 1 : 0);
    }, 0);

    const stage1 = Math.round((correctBasics / Math.max(bundle.basics.length, 1)) * 100);
    
    let stage2 = 0;
    if (!isTest2Skipped) {
      const deepScore = bundle.deep.reduce((score, challenge) => {
        const code = (codeByChallenge[challenge.id] || "").toLowerCase();
        const hitCount = challenge.expectedSignals.filter((signal) => code.includes(signal.toLowerCase())).length;
        const implementationBonus = code.length > 30 ? 20 : 0;
        return score + Math.min(100, Math.round((hitCount / Math.max(challenge.expectedSignals.length, 1)) * 80 + implementationBonus));
      }, 0);
      stage2 = Math.round(deepScore / Math.max(bundle.deep.length, 1));
    }

    const stage3 = voiceCompleted ? Math.max(0, Math.min(100, Math.round(voiceStage3Score))) : 0;

    // Combine tests into a single trust score (0-100).
    // Test 1 is mandatory. Test 2 and Test 3 can be skipped, but skipping caps the score ceiling.
    let total = 0;
    if (!isTest2Skipped && !isVoiceSkipped) {
      total = Math.round(stage1 * 0.30 + stage2 * 0.40 + stage3 * 0.30);
    } else if (isTest2Skipped && !isVoiceSkipped) {
      total = Math.round(stage1 * 0.45 + stage3 * 0.55);
      total = Math.min(total, 85);
    } else if (!isTest2Skipped && isVoiceSkipped) {
      total = Math.round(stage1 * 0.45 + stage2 * 0.55);
      total = Math.min(total, 85);
    } else {
      total = Math.round(stage1 * 0.70);
      total = Math.min(total, 70);
    }
      
    // Apply cheating penalty
    total = Math.max(0, total - Math.floor(cheatScore / 2));

    onComplete({ stage1, stage2, stage3, total, cheatingScore: cheatScore });
  };

  if (loading || !bundle) {
    return (
      <div className="grid min-h-[460px] place-items-center rounded-[2rem] border border-[var(--border)] bg-white/90 p-10 text-center shadow-xl dark:bg-white/5">
        <div>
          <Loader2 className="mx-auto mb-5 animate-spin text-orange-600" size={38} />
          <h3 className="font-display text-3xl font-black text-slate-950 dark:text-white">Generating three-stage assessment</h3>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
            Building basics, deep theory, CP tasks, and the agentic voice interview stage.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-[2rem] border border-[var(--border)] bg-white/90 p-5 shadow-2xl shadow-slate-950/5 dark:bg-white/5 md:p-7 relative">
      <CheatingDetector onTelemetryUpdate={(data) => setTelemetry(data)} />
      
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-orange-600">Dynamic assessment</p>
          <h3 className="mt-2 font-display text-4xl font-black text-slate-950 dark:text-white">
            Prove the trust score
          </h3>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-300">
            Test 1 (Basics) is mandatory. Test 2 (Deep + CP) and Test 3 (Voice Interview) improve match quality, but can be skipped with a score cap.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3 rounded-2xl bg-slate-100 p-2 dark:bg-black/30">
          <button
            type="button"
            onClick={() => setActiveTab("basics")}
            className={`rounded-xl px-4 py-3 text-sm font-black transition ${
              activeTab === "basics" ? "bg-white text-orange-600 shadow-lg dark:bg-white dark:text-slate-950" : "text-slate-600 dark:text-slate-300"
            }`}
          >
            Test 1: Basics {completion.basics}%
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("deep")}
            className={`rounded-xl px-4 py-3 text-sm font-black transition ${
              activeTab === "deep" ? "bg-white text-orange-600 shadow-lg dark:bg-white dark:text-slate-950" : "text-slate-600 dark:text-slate-300"
            }`}
          >
            Test 2: Deep {isTest2Skipped ? "(Skipped)" : `${completion.deep}%`}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("voice")}
            className={`rounded-xl px-4 py-3 text-sm font-black transition ${
              activeTab === "voice" ? "bg-white text-orange-600 shadow-lg dark:bg-white dark:text-slate-950" : "text-slate-600 dark:text-slate-300"
            }`}
          >
            Test 3: Voice {isVoiceSkipped ? "(Skipped)" : completion.voice ? "100%" : ""}
          </button>
        </div>
      </div>

      {activeTab === "basics" ? (
        <div className="mt-8 grid gap-4">
          {bundle.basics.map((question, index) => (
            <article key={question.id} className="rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-white/10 dark:bg-white/5">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <span className="text-xs font-black uppercase tracking-[0.2em] text-orange-600">
                    Q{index + 1} - {question.skill}
                  </span>
                  <h4 className="mt-2 text-lg font-black text-slate-950 dark:text-white">{question.prompt}</h4>
                </div>
                <Brain className="shrink-0 text-orange-500" />
              </div>

              {question.type === "mcq" && question.options?.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {question.options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setAnswers((previous) => ({ ...previous, [question.id]: option }))}
                      className={`rounded-2xl border px-4 py-3 text-left text-sm font-semibold transition hover:-translate-y-1 ${
                        answers[question.id] === option
                          ? "border-orange-400 bg-orange-50 text-orange-700 shadow-lg dark:bg-orange-500/10"
                          : "border-slate-200 bg-white text-slate-700 dark:border-white/10 dark:bg-black/20 dark:text-slate-200"
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  value={answers[question.id] || ""}
                  onChange={(event) => setAnswers((previous) => ({ ...previous, [question.id]: event.target.value }))}
                  className="min-h-28 w-full rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none focus:border-orange-400 dark:border-white/10 dark:bg-black/20 dark:text-white"
                  placeholder="Write a concise answer..."
                />
              )}
            </article>
          ))}
        </div>
      ) : activeTab === "deep" ? (
        <div className="mt-8 grid gap-6">
          {!isTest2Skipped ? (
            <>
              <div className="flex justify-end mb-2">
                 <button onClick={() => setIsTest2Skipped(true)} className="text-sm font-bold text-slate-500 hover:text-slate-800 underline">Skip Test 2 (Max score will be capped)</button>
              </div>
              {bundle.deep.map((challenge) => (
                <article key={challenge.id} className="grid gap-5 lg:grid-cols-[0.88fr_1.12fr]">
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 dark:border-white/10 dark:bg-white/5">
                    <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-slate-950 px-3 py-2 text-xs font-black uppercase tracking-[0.18em] text-white dark:bg-white dark:text-slate-950">
                      <Code2 size={15} />
                      {challenge.difficulty}
                    </div>
                    <h4 className="font-display text-3xl font-black text-slate-950 dark:text-white">{challenge.title}</h4>
                    <p className="mt-4 text-sm leading-7 text-slate-600 dark:text-slate-300">{challenge.prompt}</p>
                    <div className="mt-6 flex flex-wrap gap-2">
                      {challenge.companyTargets.map((company) => (
                        <span
                          key={company}
                          className="rounded-full border border-orange-200 bg-orange-50 px-3 py-2 text-xs font-black uppercase tracking-[0.2em] text-orange-700 dark:border-orange-300/20 dark:bg-orange-300/10 dark:text-orange-200"
                        >
                          {company}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <MonacoCodeEditor
                      language="python"
                      value={codeByChallenge[challenge.id] || challenge.starterCode}
                      onChange={(value) => setCodeByChallenge((previous) => ({ ...previous, [challenge.id]: value }))}
                    />
                    <div className="flex justify-end">
                      <button onClick={() => handleRunCode(challenge.id)} className="flex items-center gap-2 bg-slate-800 text-white px-4 py-2 rounded-xl hover:bg-slate-700 text-sm font-bold">
                        <Play size={14} /> Run Code
                      </button>
                    </div>
                    {executionResults[challenge.id] && (
                      <div className={`mt-2 p-3 rounded-xl text-xs font-mono ${executionResults[challenge.id].error ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' : 'bg-slate-100 text-slate-800 dark:bg-black/40 dark:text-slate-300'}`}>
                        {executionResults[challenge.id].stdout && <div>{executionResults[challenge.id].stdout}</div>}
                        {executionResults[challenge.id].stderr && <div className="text-red-500">{executionResults[challenge.id].stderr}</div>}
                      </div>
                    )}
                  </div>
                </article>
              ))}
            </>
          ) : (
             <div className="text-center py-10">
               <p className="text-lg font-bold text-slate-600 dark:text-slate-300">You have opted to skip Test 2.</p>
               <button onClick={() => setIsTest2Skipped(false)} className="mt-4 text-orange-600 hover:underline">Changed your mind? Take Test 2</button>
             </div>
          )}
        </div>
      ) : (
        <div className="mt-8 grid gap-6">
          <section className="rounded-3xl border border-slate-200 bg-slate-50 p-6 dark:border-white/10 dark:bg-white/5">
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.2em] text-orange-600">Test 3: Agentic Voice Interview</p>
                <h4 className="mt-2 font-display text-3xl font-black text-slate-950 dark:text-white">Answer 5 questions live</h4>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  This stage measures confidence, clarity, and domain readiness. Your voice agent will ask exactly 5 questions and generate an evaluation report.
                </p>
              </div>
              <Mic className="shrink-0 text-orange-500" />
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <label className="text-xs font-black uppercase tracking-[0.16em] text-slate-500 dark:text-slate-300">
                Your Full Name
                <input
                  type="text"
                  value={voiceCandidateName}
                  onChange={(event) => setVoiceCandidateName(event.target.value)}
                  placeholder="Enter your full name"
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-orange-400 dark:border-white/10 dark:bg-black/20 dark:text-white"
                />
              </label>

              <label className="text-xs font-black uppercase tracking-[0.16em] text-slate-500 dark:text-slate-300">
                Internship Domain
                <select
                  value={voiceDomain}
                  onChange={(event) => setVoiceDomain(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-orange-400 dark:border-white/10 dark:bg-black/20 dark:text-white"
                >
                  {VOICE_DOMAIN_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-black/20">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm font-bold text-slate-800 dark:text-slate-200">
                  Status: <span className="text-slate-600 dark:text-slate-300">{voiceStatus}</span>
                </div>
                <div className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                  Candidate ID: <span className="font-mono">{voiceCandidateId ? `${voiceCandidateId.slice(0, 8)}...` : "pending"}</span>
                </div>
              </div>
              {voiceSession?.status === "completed" && (
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                  Voice score: <strong className="text-slate-900 dark:text-white">{voiceStage3Score}/100</strong>. You can open the full report any time.
                </p>
              )}
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={launchVoiceInterview}
                  disabled={voiceLaunching}
                  className="inline-flex items-center justify-center gap-3 rounded-2xl bg-slate-950 px-6 py-4 text-sm font-black uppercase tracking-[0.2em] text-white transition hover:-translate-y-1 hover:bg-orange-600 disabled:cursor-wait disabled:opacity-60 dark:bg-white dark:text-slate-950"
                >
                  <Mic size={18} />
                  {voiceLaunching ? "Launching..." : "Start Voice Interview"}
                </button>

                <button
                  type="button"
                  onClick={() => void pollVoiceSession()}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm font-black uppercase tracking-[0.2em] text-slate-700 transition hover:-translate-y-1 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
                >
                  <RefreshCw size={18} />
                  Refresh status
                </button>

                {voiceSession?.status === "completed" && voiceApiBase && (
                  <a
                    className="inline-flex items-center justify-center gap-2 rounded-2xl border border-orange-200 bg-orange-50 px-5 py-4 text-sm font-black uppercase tracking-[0.2em] text-orange-700 transition hover:-translate-y-1 dark:border-orange-300/20 dark:bg-orange-300/10 dark:text-orange-200"
                    href={`${voiceApiBase}/interview/result?id=${encodeURIComponent(voiceCandidateId)}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={18} />
                    View report
                  </a>
                )}
              </div>

              {!voiceSession?.status || voiceSession.status !== "completed" ? (
                <button
                  type="button"
                  onClick={() => setIsVoiceSkipped(true)}
                  className="text-sm font-bold text-slate-500 hover:text-slate-800 underline dark:hover:text-slate-200"
                >
                  Skip Test 3 (Max score will be capped)
                </button>
              ) : null}
            </div>

            <div className={`mt-6 rounded-2xl border border-cyan-300/30 bg-slate-950/70 p-4 ${voiceWidgetVisible ? "" : "hidden"}`}>
                <p className="mb-3 text-xs font-black uppercase tracking-[0.2em] text-cyan-300">
                  Live Voice Assistant
                </p>
                <p className="mb-4 text-sm text-slate-300">
                  If prompted, allow microphone access. Click once inside the widget to start audio if needed.
                </p>
                <div className="flex justify-center">
                  <div
                    id="omni-widget-component"
                    style={{ width: "70%", height: "500px" }}
                    className="rounded-xl border border-slate-700/70 bg-black/30 p-2"
                  />
                </div>
              </div>
          </section>

          {isVoiceSkipped && (
            <div className="text-center py-6">
              <p className="text-lg font-bold text-slate-600 dark:text-slate-300">You have opted to skip Test 3.</p>
              <button onClick={() => setIsVoiceSkipped(false)} className="mt-3 text-orange-600 hover:underline">Changed your mind? Take Test 3</button>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          className="rounded-2xl border border-slate-200 bg-white px-6 py-4 text-sm font-black uppercase tracking-[0.2em] text-slate-600 transition hover:-translate-y-1 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
        >
          Back
        </button>
        <button
          type="button"
          onClick={submitAssessment}
          className="inline-flex items-center justify-center gap-3 rounded-2xl bg-orange-600 px-6 py-4 text-sm font-black uppercase tracking-[0.2em] text-white shadow-xl shadow-orange-500/20 transition hover:-translate-y-1 hover:bg-orange-500"
        >
          <CheckCircle2 size={18} />
          Submit & Generate Dashboard
        </button>
      </div>
    </div>
  );
}
