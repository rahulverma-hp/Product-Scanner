// src/pages/ScannerPage.tsx
import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { BrowserBarcodeReader } from "@zxing/library";
import { Card } from "../components/Card";
import { deleteProfile, me, scanPackagePhoto, scanProduct } from "../api";

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

interface ProfileEvaluation {
  profile_type?: string | null;
  username?: string | null;
  weight_kg?: number | null;
  daily_sugar_limit_g?: number | null;
  sugar_per_100g?: number | null;
  sugar_percentage_of_daily_limit?: number | null;
  recommendation?: string | null;
  summary?: string | null;
}

interface HealthBlock {
  good_ingredients?: string[];
  bad_ingredients?: string[];
  high_nutrients?: { nutrient: string; amount_per_100g: number }[];
  pros?: string[];
  cons?: string[];
  generic_summary?: string;
  profile_evaluation?: ProfileEvaluation | null;
  ai_advice?: string;
  ai_advice_error?: string;
}

interface ScanProfile {
  id?: number;
  username?: string;
  display_name?: string | null;
  name?: string;
  age?: number;
  gender?: string;
  height_cm?: number;
  weight_kg?: number;
  type?: string;
}

interface PersonalisedAdvice {
  personalised_summary?: string;
  source?: string;
  disclaimer?: string;
}

interface ScanResultData {
  product_name: string;
  brand: string;
  ingredients: string;
  health: HealthBlock;
  ai_analysis?: any;
  ai_analysis_error?: string | null;
  hf_insights?: HfInsights | null;
  ml_prediction?: {
    health_tier?: string;
    tier?: string;
    label?: string;
    confidence?: number;
    flags?: Record<string, { active?: boolean; confidence?: number }>;
  } | null;
  ml_prediction_error?: string | null;
  personalised?: PersonalisedAdvice | null;
  package_scan?: { ingredients_text?: string | null; error?: string } | null;
  profile?: ScanProfile | null;
  data_source?: "openfoodfacts" | "foodrepo" | string;
}

interface NerEntity {
  word?: string;
  entity_group?: string;
  score?: number;
}

interface HfInsights {
  ingredient_ner?: {
    model?: string;
    status?: string;
    message?: string;
    entities?: NerEntity[];
    risk_entities?: NerEntity[];
    positive_entities?: NerEntity[];
    risk_flags?: string[];
    positive_flags?: string[];
    error?: string;
  };
  category_prediction?: {
    model?: string;
    source?: string;
    category_names?: string[];
    categories?: { name?: string; score?: number | null }[];
    error?: string;
  };
}

function ResultSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const headingId = React.useId();
  return (
    <section className="result-section" aria-labelledby={headingId}>
      <h3 className="result-section-title" id={headingId}>
        {title}
      </h3>
      <div className="result-section-body">{children}</div>
    </section>
  );
}

function ChipList({ items, variant }: { items: string[]; variant: "good" | "bad" }) {
  if (!items.length) {
    return <p className="result-muted">None detected</p>;
  }
  return (
    <ul className="result-chip-list" role="list">
      {items.map((t) => (
        <li key={t} className={`result-chip result-chip--${variant}`}>
          {t}
        </li>
      ))}
    </ul>
  );
}

function ResultDetails({
  summary,
  defaultOpen,
  children,
}: {
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  // Use controlled `open` — older @types/react don't include `defaultOpen` on <details>.
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <details
      className="result-details"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="result-details-summary">{summary}</summary>
      <div className="result-details-body">{children}</div>
    </details>
  );
}

function formatCategoryName(name: string) {
  return name.replace(/^en:/i, "").replace(/-/g, " ").trim();
}

function mapScanResponse(data: any): ScanResultData {
  const ingredients =
    data.ingredients?.trim() ||
    data.package_scan?.ingredients_text?.trim() ||
    "";
  return {
    product_name: data.product_name ?? "Unknown product",
    brand: data.brand ?? "Unknown brand",
    ingredients,
    health: data.health ?? {},
    ai_analysis: data.ai_analysis ?? null,
    ai_analysis_error: data.ai_analysis_error ?? null,
    hf_insights: data.hf_insights ?? null,
    ml_prediction: data.ml_prediction ?? null,
    ml_prediction_error: data.ml_prediction_error ?? null,
    personalised: data.personalised ?? null,
    package_scan: data.package_scan ?? null,
    profile: data.profile ?? null,
    data_source: data.data_source,
  };
}

function DataSourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  const label =
    source === "openfoodfacts"
      ? "Open Food Facts"
      : source === "foodrepo"
        ? "Open Food Repo"
        : source;
  return (
    <span className={`result-source-badge result-source-badge--${source}`} title="Where this product data came from">
      {label}
    </span>
  );
}

function HealthAnalysisBlock({ health }: { health: HealthBlock }) {
  const h = health || {};
  const pros = h.pros ?? [];
  const cons = h.cons ?? [];
  const narrative = (h.generic_summary || "").trim();
  const hasStructured = pros.length > 0 || cons.length > 0;

  if (!hasStructured && !narrative) {
    return <p className="result-muted">No health summary available.</p>;
  }

  return (
    <div className="result-interactive-stack">
      {pros.length > 0 && (
        <ResultDetails summary="Positives" defaultOpen>
          <ul className="result-bullet result-bullet--pros">
            {pros.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </ResultDetails>
      )}
      {cons.length > 0 && (
        <ResultDetails summary="Concerns" defaultOpen>
          <ul className="result-bullet result-bullet--cons">
            {cons.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </ResultDetails>
      )}
      {narrative && (
        <ResultDetails summary="Full summary (all notes)" defaultOpen={!hasStructured}>
          <p className="result-summary result-summary--block">{narrative}</p>
        </ResultDetails>
      )}
    </div>
  );
}

function SugarMeter({
  percentage,
  sugarG,
  limitG,
}: {
  percentage: number | null | undefined;
  sugarG: number | null | undefined;
  limitG: number | null | undefined;
}) {
  const pct = typeof percentage === "number" && !Number.isNaN(percentage) ? percentage : null;
  const width = pct == null ? 0 : Math.min(100, Math.max(0, pct));
  let tone = "ok";
  if (pct != null) {
    if (pct >= 50) tone = "high";
    else if (pct >= 20) tone = "mid";
  }

  return (
    <div className="sugar-meter">
      <div className="sugar-meter-labels">
        <span>Sugar vs your day</span>
        {pct != null && (
          <span className="sugar-meter-pct">
            {pct}% of daily sugar guide
            {pct > 100 ? " (over guide)" : ""}
          </span>
        )}
      </div>
      <div className="sugar-meter-track" role="presentation">
        <div
          className={`sugar-meter-fill sugar-meter-fill--${tone}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <div className="sugar-meter-stats">
        {sugarG != null && (
          <span>
            In this product (per 100 g): <strong>{sugarG} g</strong> sugar
          </span>
        )}
        {limitG != null && (
          <span className="result-muted">
            Your guide: ~<strong>{limitG} g</strong>/day (estimate)
          </span>
        )}
      </div>
    </div>
  );
}

function ProfileForYouBlock({
  pe,
  profile,
}: {
  pe: ProfileEvaluation;
  profile?: ScanProfile | null;
}) {
  const username =
    pe.username?.trim() ||
    profile?.display_name?.trim() ||
    profile?.username?.trim() ||
    profile?.name?.trim() ||
    "Your profile";
  const rec = pe.recommendation?.trim();

  return (
    <div className="result-interactive-stack">
      <div className="profile-you-card">
        <p className="profile-you-label">Personalised for</p>
        <p className="profile-you-name">{username}</p>
        {profile?.age != null && profile?.gender && (
          <p className="result-muted profile-you-meta">
            {profile.age} yrs ·{" "}
            {profile.gender.charAt(0).toUpperCase() + profile.gender.slice(1)}
          </p>
        )}
        <p className="result-muted profile-you-footnote">
          Sugar limits are estimated from age and gender — not medical advice.
        </p>
      </div>

      {(pe.daily_sugar_limit_g != null || pe.sugar_per_100g != null) && (
        <ResultDetails summary="Sugar snapshot" defaultOpen>
          <SugarMeter
            percentage={pe.sugar_percentage_of_daily_limit}
            sugarG={pe.sugar_per_100g ?? undefined}
            limitG={pe.daily_sugar_limit_g ?? undefined}
          />
          {rec && <p className="result-recommendation-pill">{rec}</p>}
        </ResultDetails>
      )}

      {pe.summary && (
        <ResultDetails summary="Advice in plain language" defaultOpen>
          <p className="result-profile-advice">{pe.summary}</p>
        </ResultDetails>
      )}
    </div>
  );
}

function ScanResultView({ data }: { data: ScanResultData }) {
  const h = data.health || {};
  const pe = h.profile_evaluation ?? null;
  const good = h.good_ingredients ?? [];
  const bad = h.bad_ingredients ?? [];
  const high = h.high_nutrients ?? [];
  const ai = data.ai_analysis || null;
  const hf = data.hf_insights ?? null;
  const ml = data.ml_prediction ?? null;
  const mlTier = ml?.health_tier ?? ml?.tier;
  const personalised = data.personalised ?? null;
  const ner = hf?.ingredient_ner;
  const foodTypes = (hf?.category_prediction?.category_names ?? [])
    .map(formatCategoryName)
    .filter(Boolean);
  const fromPhoto =
    !!data.package_scan?.ingredients_text ||
    (data.data_source ?? "").includes("package_photo");

  return (
    <div className="result-panel">
      <ResultSection title="Product">
        <div className="result-product-header">
          <DataSourceBadge source={data.data_source} />
          {fromPhoto ? (
            <span className="result-source-badge result-source-badge--package_photo">
              Label photo
            </span>
          ) : null}
        </div>
        <p className="result-product-name">{data.product_name}</p>
        <p className="result-brand">{data.brand}</p>
      </ResultSection>

      {pe ? (
        <ResultSection title="For you">
          <ProfileForYouBlock pe={pe} profile={data.profile} />
        </ResultSection>
      ) : null}

      {mlTier ? (
        <ResultSection title="Quick health rating">
          <p className="result-summary result-summary--block">
            <strong style={{ textTransform: "capitalize" }}>{mlTier}</strong>
            {typeof ml?.confidence === "number"
              ? ` — ${Math.round(ml.confidence * 100)}% model confidence`
              : ""}
          </p>
          {ml?.flags && Object.keys(ml.flags).length > 0 ? (
            <ResultDetails summary="What the model noticed">
              <ul className="result-nutrient-list">
                {Object.entries(ml.flags).map(([flag, info]) => (
                  <li key={flag}>
                    <strong>{flag.replace(/_/g, " ")}</strong>
                    <span className="result-muted">
                      {" "}
                      — {info?.active ? "likely present" : "unlikely"}
                    </span>
                  </li>
                ))}
              </ul>
            </ResultDetails>
          ) : null}
        </ResultSection>
      ) : data.ml_prediction_error ? (
        <ResultSection title="Quick health rating">
          <p className="result-muted">{data.ml_prediction_error}</p>
        </ResultSection>
      ) : null}

      <ResultSection title="Health summary">
        <HealthAnalysisBlock health={h} />
      </ResultSection>

      {personalised?.personalised_summary ? (
        <ResultSection title="Personalised advice">
          <p className="result-summary result-summary--block">
            {personalised.personalised_summary}
          </p>
          {personalised.disclaimer ? (
            <p className="result-muted" style={{ marginTop: 8 }}>
              {personalised.disclaimer}
            </p>
          ) : null}
        </ResultSection>
      ) : null}

      <ResultSection title="Ingredients">
        <p className="result-ingredients">
          {data.ingredients?.trim() || "No ingredient information available."}
        </p>
      </ResultSection>

      <ResultSection title="Ingredient signals">
        <p className="result-subheading">Better / positive signals</p>
        <ChipList items={good} variant="good" />
        <p className="result-subheading result-subheading--spaced">Less healthy signals</p>
        <ChipList items={bad} variant="bad" />
        {ner?.status === "loading" && ner.message ? (
          <p className="result-muted" style={{ marginTop: 10 }}>
            {ner.message}
          </p>
        ) : null}
      </ResultSection>

      {foodTypes.length > 0 ? (
        <ResultSection title="Food type">
          <ChipList items={foodTypes} variant="good" />
        </ResultSection>
      ) : null}

      <ResultSection title="Nutrients high per 100 g">
        {high.length === 0 ? (
          <p className="result-muted">No nutrients flagged as high.</p>
        ) : (
          <ul className="result-nutrient-list">
            {high.map((n) => (
              <li key={n.nutrient}>
                <strong>{n.nutrient}</strong>
                <span className="result-muted"> — {n.amount_per_100g} g / 100 g</span>
              </li>
            ))}
          </ul>
        )}
      </ResultSection>

      {ai ? (
        <ResultSection title="AI analysis (personalised)">
          <ResultDetails summary="Overall score" defaultOpen>
            <p className="result-summary result-summary--block">
              <strong>
                {ai?.overall_score?.score ?? "—"}/100
              </strong>{" "}
              {ai?.overall_score?.label ? `(${ai.overall_score.label})` : ""}{" "}
              {ai?.overall_score?.one_line ? `— ${ai.overall_score.one_line}` : ""}
            </p>
          </ResultDetails>

          <ResultDetails summary="Good ingredients" defaultOpen>
            {(ai?.sections?.ingredients?.good || []).length ? (
              <ul className="result-nutrient-list">
                {(ai.sections.ingredients.good as any[]).map((x, idx) => (
                  <li key={`${x?.name ?? "good"}-${idx}`}>
                    <strong>{x?.name ?? "—"}</strong>
                    {x?.why ? <div className="result-muted">{x.why}</div> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="result-muted">None highlighted as beneficial.</p>
            )}
          </ResultDetails>

          <ResultDetails summary="Bad / risky ingredients" defaultOpen>
            {(ai?.sections?.ingredients?.bad || []).length ? (
              <ul className="result-nutrient-list">
                {(ai.sections.ingredients.bad as any[]).map((x, idx) => (
                  <li key={`${x?.name ?? "bad"}-${idx}`}>
                    <strong>{x?.name ?? "—"}</strong>
                    {x?.risk_level ? (
                      <span className="result-muted"> — risk: {x.risk_level}</span>
                    ) : null}
                    {x?.why ? <div className="result-muted">{x.why}</div> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="result-muted">No specific risky ingredients flagged.</p>
            )}
          </ResultDetails>

          <ResultDetails summary="Unknown products">
            {(ai?.sections?.ingredients?.neutral_or_unknown || []).length ? (
              <ul className="result-nutrient-list">
                {(ai.sections.ingredients.neutral_or_unknown as any[]).map((x, idx) => (
                  <li key={`${x?.name ?? "neutral"}-${idx}`}>
                    <strong>{x?.name ?? "—"}</strong>
                    {x?.what_it_is ? (
                      <div className="result-muted">{x.what_it_is}</div>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="result-muted">No unknown ingredients highlighted.</p>
            )}
          </ResultDetails>

          <ResultDetails summary="Nutrition notes">
            {(ai?.sections?.nutrition?.notes || []).length ? (
              <ul className="result-bullet">
                {(ai.sections.nutrition.notes as any[]).map((n, idx) => (
                  <li key={`note-${idx}`}>{String(n)}</li>
                ))}
              </ul>
            ) : (
              <p className="result-muted">No extra nutrition notes.</p>
            )}
          </ResultDetails>

          <ResultDetails summary="Advice for you" defaultOpen>
            <p className="result-summary result-summary--block">
              {ai?.sections?.profile_advice?.for_user ?? "—"}
            </p>
            {ai?.sections?.profile_advice?.recommended_max_per_day ? (
              <p className="result-recommendation-pill">
                <strong>Recommended max per day:</strong>{" "}
                {ai.sections.profile_advice.recommended_max_per_day}
              </p>
            ) : null}
            {(ai?.sections?.profile_advice?.watch_out_for || []).length ? (
              <ResultDetails summary="Watch out for">
                <ul className="result-bullet">
                  {(ai.sections.profile_advice.watch_out_for as any[]).map((w, idx) => (
                    <li key={`watch-${idx}`}>{String(w)}</li>
                  ))}
                </ul>
              </ResultDetails>
            ) : null}
          </ResultDetails>

          {ai?.disclaimer ? (
            <p className="result-muted" style={{ marginTop: 10 }}>
              {ai.disclaimer}
            </p>
          ) : null}
        </ResultSection>
      ) : (
        <ResultSection title="AI analysis">
          <p className="result-muted">
            {data.ai_analysis_error ||
              "No AI analysis returned for this scan."}
          </p>
        </ResultSection>
      )}

    </div>
  );
}

export const ScannerPage: React.FC = () => {
  const query = useQuery();
  const nav = useNavigate();
  const [scanning, setScanning] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResultData | null>(null);
  const [viewerUsername, setViewerUsername] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [guestMode, setGuestMode] = useState(false);
  const [lastBarcode, setLastBarcode] = useState("");
  const [photoBarcode, setPhotoBarcode] = useState("");

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const codeReaderRef = useRef<BrowserBarcodeReader | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const guest = localStorage.getItem("guest_mode") === "1";
    setGuestMode(guest);
    if (guest) {
      setToken(null);
      setViewerUsername("Guest");
      setError(null);
      setResult(null);
      setHint(null);
      return;
    }
    const t = localStorage.getItem("auth_token");
    setToken(t);
    if (!t) {
      setViewerUsername(null);
      setError("Please sign in first.");
      setResult(null);
      setHint(null);
      return;
    }
    setError(null);
    me(t)
      .then((data) => setViewerUsername(data.profile.username))
      .catch(() => {
        localStorage.removeItem("auth_token");
        setToken(null);
        setViewerUsername(null);
        setError("Session expired. Please sign in again.");
      });
  }, []);

  const handleScan = async () => {
    if (scanning) return;
    if (!guestMode && !token) {
      alert("Please sign in first.");
      return;
    }
    if (!videoRef.current) return;

    setScanning(true);
    setHint("Starting camera…");
    setError(null);
    setResult(null);

    const reader = new BrowserBarcodeReader();
    codeReaderRef.current = reader;

    try {
      await reader.decodeFromVideoDevice(
        null,
        videoRef.current,
        async (res) => {
          if (res) {
            const barcode = res.getText();
            setScanning(false);
            reader.reset();
            setHint("Fetching product…");
            try {
              const data = await scanProduct(barcode, token);
              setHint(null);
              setLastBarcode(barcode);
              setPhotoBarcode(barcode);
              setResult(mapScanResponse(data));
            } catch (e) {
              console.error(e);
              setHint(null);
              setError(
                e instanceof Error
                  ? e.message
                  : "Failed to fetch product info from server."
              );
            }
          }
        }
      );
    } catch (e) {
      console.error(e);
      setHint(null);
      setError("Failed to start camera.");
      setScanning(false);
    }
  };

  const handlePhotoSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!guestMode && !token) {
      alert("Please sign in first.");
      return;
    }
    setHint("Reading package label…");
    setError(null);
    setResult(null);
    try {
      const data = await scanPackagePhoto(
        file,
        photoBarcode.trim() || lastBarcode || undefined,
        token
      );
      setHint(null);
      setResult(mapScanResponse(data));
      if (
        data.package_scan?.error &&
        !data.ingredients &&
        !data.package_scan?.ingredients_text
      ) {
        setError(data.package_scan.error);
      }
    } catch (err) {
      setHint(null);
      setError(err instanceof Error ? err.message : "Failed to read package photo.");
    } finally {
      if (photoInputRef.current) {
        photoInputRef.current.value = "";
      }
    }
  };

  const handleBack = () => {
    localStorage.removeItem("guest_mode");
    localStorage.removeItem("auth_token");
    nav("/login");
  };

  const handleExitGuest = () => {
    localStorage.removeItem("guest_mode");
    nav("/login");
  };

  const handleDeleteProfile = async () => {
    if (!token) return;
    const ok = window.confirm(
      "Delete your profile permanently? This cannot be undone."
    );
    if (!ok) return;
    try {
      await deleteProfile(token);
      localStorage.removeItem("auth_token");
      localStorage.removeItem("guest_mode");
      nav("/login");
    } catch (e: any) {
      alert(e?.message || "Failed to delete profile.");
    }
  };

  const profileLine =
    guestMode ? "Using as guest" : viewerUsername ? `Signed in as ${viewerUsername}` : "Not signed in";

  return (
    <div className="app-root scanner-page">
      <div className="scanner-layout">
        <div className="scanner-column">
          <Card title="Scan a product">
            <p className="small" style={{ marginBottom: 8 }}>
              {profileLine}
            </p>
            <div className="scanner-actions">
              <button className="button" onClick={handleScan} disabled={scanning}>
                {scanning ? "Scanning…" : "Start scan"}
              </button>
              {guestMode && (
                <button className="button secondary" onClick={handleExitGuest}>
                  Exit guest / Login
                </button>
              )}
              {!guestMode && token && (
                <button className="button secondary" onClick={handleDeleteProfile}>
                  Delete profile
                </button>
              )}
              <button className="button secondary" onClick={handleBack}>
                Change profile
              </button>
            </div>
            <div className="scanner-video-wrap">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="scanner-video"
              />
              <div className="scanner-video-focus" />
            </div>

            <div className="scanner-photo-section">
              <p className="scanner-photo-title">Can&apos;t read the label?</p>
              <p className="result-muted scanner-photo-hint">
                Upload a clear photo of the ingredients list. Add a barcode below if you
                have one — it helps match the product.
              </p>
              <label className="scanner-photo-label" htmlFor="package-photo-input">
                Barcode (optional)
              </label>
              <input
                id="package-photo-barcode"
                className="scanner-photo-input"
                type="text"
                inputMode="numeric"
                placeholder="e.g. 3017620422003"
                value={photoBarcode}
                onChange={(e) => setPhotoBarcode(e.target.value)}
              />
              <input
                id="package-photo-input"
                ref={photoInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                className="scanner-photo-file"
                onChange={handlePhotoSelected}
              />
              <button
                type="button"
                className="button secondary scanner-photo-button"
                onClick={() => photoInputRef.current?.click()}
              >
                Read label from photo
              </button>
            </div>
          </Card>
        </div>

        <div className="scanner-column">
          <Card title="Result">
            {hint && !error && !result && (
              <p className="result-placeholder">{hint}</p>
            )}
            {error && <p className="result-error">{error}</p>}
            {!hint && !error && !result && (
              <p className="result-placeholder">
                Scan a barcode — results are grouped into clear sections. Use the ▼ panels to expand health notes and
                profile advice.
              </p>
            )}
            {result && <ScanResultView data={result} />}
          </Card>
        </div>
      </div>
    </div>
  );
};
