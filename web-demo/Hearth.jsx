import React, { useState, useEffect, useRef } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { PenLine, BarChart3, Target, AlertTriangle, TrendingUp } from "lucide-react";

// ---------------------------------------------------------------- design tokens
const COLORS = {
  ink: "#1F2A24",
  parchment: "#FAF6EE",
  surface: "#FFFFFF",
  gold: "#B98B2E",
  sage: "#6B8F71",
  terracotta: "#B5533C",
  hairline: "#E3DCC9",
  muted: "#9A9286",
};
const SERIF = "Georgia, 'Times New Roman', serif";
const MONO = "'SF Mono', 'Consolas', ui-monospace, monospace";

const CATEGORIES = [
  "Food Delivery", "Groceries", "Travel", "Entertainment",
  "Shopping", "Bills & Utilities", "Food & Dining", "Other",
];

const CATEGORY_KEYWORDS = {
  "Food Delivery": ["swiggy", "zomato", "uber eats"],
  Groceries: ["bigbasket", "blinkit", "zepto", "grocery", "groceries"],
  Travel: ["uber", "ola", "rapido", "flight", "train", "irctc"],
  Entertainment: ["movie", "netflix", "spotify", "prime", "concert"],
  Shopping: ["amazon", "myntra", "flipkart", "shopping"],
  "Bills & Utilities": ["electricity", "wifi", "recharge", "rent", "bill"],
  "Food & Dining": ["lunch", "dinner", "breakfast", "restaurant", "cafe", "coffee"],
};

// ---------------------------------------------------------------- parsing (extract)
function regexFallbackParse(text) {
  const amounts = text.match(/\d+(\.\d+)?/g);
  let amount = amounts ? parseFloat(amounts[0]) : 0;

  const splitMatch = text.match(/split\s*(\d+)/i);
  if (splitMatch) {
    const n = parseInt(splitMatch[1], 10);
    if (n > 0) amount = amount / n;
  }

  const lower = text.toLowerCase();
  let category = "Other";
  let merchant = null;
  for (const [cat, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    const hit = keywords.find((kw) => lower.includes(kw));
    if (hit) {
      category = cat;
      merchant = hit.charAt(0).toUpperCase() + hit.slice(1);
      break;
    }
  }
  return { amount: Math.round(amount * 100) / 100, category, merchant };
}

function normalize(parsed) {
  const category = CATEGORIES.includes(parsed.category) ? parsed.category : "Other";
  const merchant = parsed.merchant ? parsed.merchant.trim() : null;
  return {
    amount: Math.round((parsed.amount || 0) * 100) / 100,
    category,
    merchant,
  };
}

async function parseWithAI(text) {
  const systemPrompt = `You are an expense-parsing engine. Given a free-text expense entry, extract structured data. Always account for bill-splitting language ("split 4 ways" means divide the total amount by the number to get the user's actual share).
Return ONLY valid JSON, no markdown, no preamble, in this exact shape:
{"amount": <number>, "category": "<one of: ${CATEGORIES.join(", ")}>", "merchant": "<string or null>"}`;

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: systemPrompt,
      messages: [{ role: "user", content: text }],
    }),
  });
  if (!response.ok) throw new Error("API request failed");
  const data = await response.json();
  const raw = data.content.find((b) => b.type === "text")?.text || "";
  const cleaned = raw.replace(/```json|```/g, "").trim();
  const parsed = JSON.parse(cleaned);
  return normalize(parsed);
}

async function parseEntry(text) {
  try {
    return await parseWithAI(text);
  } catch (e) {
    return normalize(regexFallbackParse(text));
  }
}

// ---------------------------------------------------------------- analytics
function categoryBreakdown(entries) {
  const totals = {};
  entries.forEach((e) => { totals[e.category] = (totals[e.category] || 0) + e.amount; });
  return Object.entries(totals)
    .map(([category, amount]) => ({ category, amount: Math.round(amount * 100) / 100 }))
    .sort((a, b) => b.amount - a.amount);
}

function monthKey(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthlyTrend(entries) {
  const totals = {};
  entries.forEach((e) => {
    const m = monthKey(e.createdAt);
    totals[m] = (totals[m] || 0) + e.amount;
  });
  return Object.entries(totals)
    .map(([month, amount]) => ({ month, amount: Math.round(amount * 100) / 100 }))
    .sort((a, b) => (a.month > b.month ? 1 : -1));
}

function detectAnomalies(entries, multiplier = 3) {
  const byCategory = {};
  entries.forEach((e) => {
    byCategory[e.category] = byCategory[e.category] || [];
    byCategory[e.category].push(e);
  });
  const anomalies = [];
  Object.entries(byCategory).forEach(([category, list]) => {
    const sorted = [...list].sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
    if (sorted.length < 4) return;
    for (let i = 3; i < sorted.length; i++) {
      const history = sorted.slice(0, i);
      const avg = history.reduce((s, e) => s + e.amount, 0) / history.length;
      const current = sorted[i];
      if (avg > 0 && current.amount >= multiplier * avg) {
        anomalies.push({
          category,
          amount: current.amount,
          average: Math.round(avg * 100) / 100,
          date: new Date(current.createdAt).toLocaleDateString(),
          merchant: current.merchant,
        });
      }
    }
  });
  return anomalies;
}

function forecastNextMonth(entries) {
  const trend = monthlyTrend(entries);
  if (trend.length < 2) return { forecast: null, message: "Log entries across 2+ months to unlock a forecast." };
  const n = trend.length;
  const xs = trend.map((_, i) => i);
  const ys = trend.map((t) => t.amount);
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = ys.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((s, x, i) => s + x * ys[i], 0);
  const sumXX = xs.reduce((s, x) => s + x * x, 0);
  const denom = n * sumXX - sumX * sumX;
  const slope = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0;
  const intercept = (sumY - slope * sumX) / n;
  const forecast = Math.max(slope * n + intercept, 0);
  const direction = slope > 0 ? "rising" : slope < 0 ? "falling" : "steady";
  return {
    forecast: Math.round(forecast * 100) / 100,
    direction,
    message: `Projected next month: ₹${Math.round(forecast).toLocaleString()} (spend is ${direction})`,
  };
}

function budgetVsActual(entries, budgets) {
  const thisMonth = monthKey(new Date().toISOString());
  const spent = {};
  entries.filter((e) => monthKey(e.createdAt) === thisMonth).forEach((e) => {
    spent[e.category] = (spent[e.category] || 0) + e.amount;
  });
  return Object.entries(budgets).map(([category, limit]) => ({
    category, spent: Math.round((spent[category] || 0) * 100) / 100, limit,
  }));
}

// ---------------------------------------------------------------- storage
async function loadUserData(username) {
  try {
    const result = await window.storage.get(`hearth:${username.toLowerCase()}`, false);
    if (result && result.value) return JSON.parse(result.value);
  } catch (e) { /* no data yet for this user */ }
  return { entries: [], budgets: {} };
}

async function saveUserData(username, entries, budgets) {
  try {
    await window.storage.set(`hearth:${username.toLowerCase()}`, JSON.stringify({ entries, budgets }), false);
    return true;
  } catch (e) {
    return false;
  }
}

// ---------------------------------------------------------------- small UI pieces
function Hairline() {
  return <div style={{ height: 1, background: COLORS.hairline, width: 64, margin: "0 auto 14px" }} />;
}

function TabButton({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-4 py-2 text-sm font-medium"
      style={{
        color: active ? COLORS.ink : COLORS.muted,
        borderBottom: active ? `2px solid ${COLORS.gold}` : "2px solid transparent",
        background: "transparent",
      }}
    >
      {icon}
      {label}
    </button>
  );
}

// ---------------------------------------------------------------- main app
export default function Hearth() {
  const [page, setPage] = useState("landing");
  const [username, setUsername] = useState("");
  const [nameDraft, setNameDraft] = useState("");
  const [activeTab, setActiveTab] = useState("log");

  const [entries, setEntries] = useState([]);
  const [budgets, setBudgets] = useState({});
  const [dataLoading, setDataLoading] = useState(false);
  const [persistFailed, setPersistFailed] = useState(false);

  const [inputText, setInputText] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");

  const [budgetCategory, setBudgetCategory] = useState(CATEGORIES[0]);
  const [budgetLimit, setBudgetLimit] = useState("");
  const [budgetStatus, setBudgetStatus] = useState("");

  const debounceRef = useRef(null);

  const enterApp = async (name) => {
    setUsername(name);
    setDataLoading(true);
    const data = await loadUserData(name);
    setEntries(data.entries || []);
    setBudgets(data.budgets || {});
    setDataLoading(false);
    setPage("app");
  };

  const switchUser = () => {
    setPage("landing");
    setNameDraft("");
    setEntries([]);
    setBudgets({});
    setInputText("");
    setPreview(null);
    setStatusMsg("");
  };

  // live preview, debounced
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!inputText.trim()) {
      setPreview(null);
      setPreviewLoading(false);
      return;
    }
    setPreviewLoading(true);
    debounceRef.current = setTimeout(async () => {
      const result = await parseEntry(inputText);
      setPreview(result);
      setPreviewLoading(false);
    }, 700);
    return () => clearTimeout(debounceRef.current);
  }, [inputText]);

  const addExpense = async () => {
    if (!inputText.trim()) {
      setStatusMsg("Type an entry first — e.g. 'Swiggy 350'.");
      return;
    }
    setAddLoading(true);
    const parsed = preview || (await parseEntry(inputText));

    if (!parsed.amount || parsed.amount <= 0) {
      setStatusMsg("Couldn't find a valid amount in that entry.");
      setAddLoading(false);
      return;
    }

    const now = new Date();
    const isRecurring = entries.some((e) => {
      if (!e.merchant || !parsed.merchant) return false;
      const sameMerchant = e.merchant.toLowerCase() === parsed.merchant.toLowerCase();
      const sameAmount = Math.abs(e.amount - parsed.amount) < 1;
      const daysSince = (now - new Date(e.createdAt)) / (1000 * 60 * 60 * 24);
      return sameMerchant && sameAmount && daysSince <= 35;
    });

    const newEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      rawText: inputText.trim(),
      amount: parsed.amount,
      category: parsed.category,
      merchant: parsed.merchant,
      isRecurring,
      createdAt: now.toISOString(),
    };

    const newEntries = [newEntry, ...entries];
    setEntries(newEntries);
    const saved = await saveUserData(username, newEntries, budgets);
    setPersistFailed(!saved);

    setStatusMsg(
      `Logged ₹${parsed.amount.toFixed(2)} under ${parsed.category}${isRecurring ? " — looks recurring" : ""}`
    );
    setInputText("");
    setPreview(null);
    setAddLoading(false);
  };

  const setBudget = async () => {
    const limit = parseFloat(budgetLimit);
    if (!budgetCategory || !limit || limit <= 0) {
      setBudgetStatus("Pick a category and a limit greater than 0.");
      return;
    }
    const newBudgets = { ...budgets, [budgetCategory]: limit };
    setBudgets(newBudgets);
    const saved = await saveUserData(username, entries, newBudgets);
    setPersistFailed(!saved);
    setBudgetStatus(`Budget set: ${budgetCategory} → ₹${limit}/month`);
    setBudgetLimit("");
  };

  // ---------------------------------------------------------------- landing
  if (page === "landing") {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: COLORS.parchment, fontFamily: "system-ui, sans-serif" }}
      >
        <div className="w-full max-w-sm text-center">
          <div style={{ fontSize: 30 }}>🕯️</div>
          <div style={{ fontFamily: SERIF, fontSize: 42, fontWeight: 700, letterSpacing: "0.06em", color: COLORS.ink, margin: "6px 0 4px" }}>
            HEARTH
          </div>
          <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 16, color: COLORS.gold, marginBottom: 14 }}>
            every rupee, explained
          </div>
          <Hairline />
          <p style={{ color: COLORS.muted, fontSize: 14, marginBottom: 18 }}>enter your name to begin</p>
          <input
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && nameDraft.trim()) enterApp(nameDraft.trim()); }}
            placeholder="✦ what's your name?"
            className="w-full px-4 py-3 mb-3 text-sm outline-none"
            style={{ background: COLORS.surface, border: `1px solid ${COLORS.hairline}`, borderRadius: 8, color: COLORS.ink }}
          />
          <button
            onClick={() => nameDraft.trim() && enterApp(nameDraft.trim())}
            disabled={!nameDraft.trim()}
            className="w-full py-3 text-sm font-medium"
            style={{
              background: nameDraft.trim() ? COLORS.ink : COLORS.hairline,
              color: nameDraft.trim() ? COLORS.parchment : COLORS.muted,
              borderRadius: 8,
            }}
          >
            Begin
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- main app
  const breakdown = categoryBreakdown(entries);
  const trend = monthlyTrend(entries);
  const anomalies = detectAnomalies(entries).slice(-5).reverse();
  const forecast = forecastNextMonth(entries);
  const budgetRows = budgetVsActual(entries, budgets);

  return (
    <div style={{ background: COLORS.parchment, minHeight: "100vh", fontFamily: "system-ui, sans-serif", color: COLORS.ink }}>
      <div className="text-center pt-9 pb-3 px-4">
        <div style={{ fontSize: 26 }}>🕯️</div>
        <div style={{ fontFamily: SERIF, fontSize: 32, fontWeight: 700, letterSpacing: "0.06em" }}>HEARTH</div>
        <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 14, color: COLORS.gold, marginBottom: 10 }}>
          every rupee, explained
        </div>
        <Hairline />
        <p style={{ fontSize: 13, color: COLORS.muted }}>
          hi, {username} · <button onClick={switchUser} style={{ textDecoration: "underline", color: COLORS.muted }}>switch user</button>
        </p>
      </div>

      <div className="flex justify-center gap-2 border-b mb-6" style={{ borderColor: COLORS.hairline }}>
        <TabButton active={activeTab === "log"} onClick={() => setActiveTab("log")} icon={<PenLine size={15} />} label="Log a Spend" />
        <TabButton active={activeTab === "insights"} onClick={() => setActiveTab("insights")} icon={<BarChart3 size={15} />} label="Insights" />
        <TabButton active={activeTab === "budgets"} onClick={() => setActiveTab("budgets")} icon={<Target size={15} />} label="Budgets" />
      </div>

      <div className="max-w-xl mx-auto px-5 pb-16">
        {persistFailed && (
          <div className="text-xs mb-4 px-3 py-2" style={{ background: "#FBEFE9", color: COLORS.terracotta, borderRadius: 6 }}>
            Couldn't save to storage — your data will work for this session but may not persist on reload.
          </div>
        )}

        {dataLoading && <p style={{ color: COLORS.muted, fontSize: 14 }}>Loading your ledger…</p>}

        {!dataLoading && activeTab === "log" && (
          <div>
            <label style={{ fontSize: 13, color: COLORS.muted }}>What did you spend on?</label>
            <input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="e.g. 'Swiggy 350' or 'movie with friends 800 split 4 ways'"
              className="w-full px-4 py-3 mt-1 mb-2 text-sm outline-none"
              style={{ background: COLORS.surface, border: `1px solid ${COLORS.hairline}`, borderRadius: 8 }}
            />

            <div
              style={{
                fontFamily: MONO, fontSize: 14, borderTop: `1px dashed ${COLORS.hairline}`,
                paddingTop: 10, marginBottom: 14, minHeight: 22,
              }}
            >
              {previewLoading ? (
                <span style={{ color: COLORS.muted, fontStyle: "italic", fontFamily: "system-ui" }}>parsing…</span>
              ) : preview && preview.amount > 0 ? (
                <span>
                  <span style={{ color: COLORS.gold, fontWeight: 600 }}>₹{preview.amount.toFixed(2)}</span>
                  {"  ·  " + preview.category}
                  {preview.merchant ? "  ·  " + preview.merchant : ""}
                </span>
              ) : (
                <span style={{ color: COLORS.muted, fontStyle: "italic", fontFamily: "system-ui" }}>
                  start typing — the parse will show up here before you log it
                </span>
              )}
            </div>

            <button
              onClick={addExpense}
              disabled={addLoading}
              className="w-full py-3 text-sm font-medium mb-3"
              style={{ background: COLORS.ink, color: COLORS.parchment, borderRadius: 8, opacity: addLoading ? 0.6 : 1 }}
            >
              {addLoading ? "Adding…" : "Add to ledger"}
            </button>

            {statusMsg && <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 16 }}>{statusMsg}</p>}

            <div style={{ borderTop: `1px solid ${COLORS.hairline}`, paddingTop: 14 }}>
              <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 8 }}>Recent entries</p>
              {entries.length === 0 ? (
                <p style={{ fontSize: 13, color: COLORS.muted, fontStyle: "italic" }}>
                  Nothing logged yet — your first entry will show up here.
                </p>
              ) : (
                <div className="space-y-2">
                  {entries.slice(0, 8).map((e) => (
                    <div key={e.id} className="flex justify-between items-baseline" style={{ fontSize: 13 }}>
                      <span style={{ color: COLORS.ink }}>
                        {e.merchant || e.rawText}
                        <span style={{ color: COLORS.muted }}> · {e.category}</span>
                        {e.isRecurring && <span style={{ color: COLORS.sage }}> · recurring</span>}
                      </span>
                      <span style={{ fontFamily: MONO, color: COLORS.gold, fontWeight: 600 }}>₹{e.amount.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!dataLoading && activeTab === "insights" && (
          <div>
            {entries.length === 0 ? (
              <p style={{ fontSize: 13, color: COLORS.muted, fontStyle: "italic" }}>
                Log a few entries to unlock insights.
              </p>
            ) : (
              <>
                <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 6 }}>Spend by category</p>
                <div style={{ height: 200, marginBottom: 24 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={breakdown}>
                      <CartesianGrid stroke={COLORS.hairline} vertical={false} />
                      <XAxis dataKey="category" tick={{ fontSize: 10, fill: COLORS.muted }} interval={0} angle={-20} textAnchor="end" height={60} />
                      <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                      <Tooltip contentStyle={{ fontSize: 12, borderColor: COLORS.hairline }} />
                      <Bar dataKey="amount" fill={COLORS.gold} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 6 }}>Monthly trend</p>
                <div style={{ height: 180, marginBottom: 24 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trend}>
                      <CartesianGrid stroke={COLORS.hairline} vertical={false} />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: COLORS.muted }} />
                      <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} />
                      <Tooltip contentStyle={{ fontSize: 12, borderColor: COLORS.hairline }} />
                      <Line type="monotone" dataKey="amount" stroke={COLORS.sage} strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={14} color={COLORS.terracotta} />
                  <p style={{ fontSize: 13, color: COLORS.muted }}>Anomalies</p>
                </div>
                {anomalies.length === 0 ? (
                  <p style={{ fontSize: 13, color: COLORS.muted, fontStyle: "italic", marginBottom: 20 }}>
                    Nothing unusual — every entry is within your normal range.
                  </p>
                ) : (
                  <div className="space-y-1 mb-5">
                    {anomalies.map((a, i) => (
                      <p key={i} style={{ fontSize: 13, color: COLORS.terracotta }}>
                        {a.date} — ₹{a.amount.toFixed(0)} on {a.category}
                        {a.merchant ? ` (${a.merchant})` : ""}, vs your usual ₹{a.average.toFixed(0)}
                      </p>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp size={14} color={COLORS.sage} />
                  <p style={{ fontSize: 13, color: COLORS.muted }}>Next month, projected</p>
                </div>
                <p style={{ fontSize: 13, color: COLORS.ink }}>{forecast.message}</p>
              </>
            )}
          </div>
        )}

        {!dataLoading && activeTab === "budgets" && (
          <div>
            <div className="flex gap-2 mb-3">
              <select
                value={budgetCategory}
                onChange={(e) => setBudgetCategory(e.target.value)}
                className="flex-1 px-3 py-2 text-sm"
                style={{ background: COLORS.surface, border: `1px solid ${COLORS.hairline}`, borderRadius: 8 }}
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <input
                type="number"
                value={budgetLimit}
                onChange={(e) => setBudgetLimit(e.target.value)}
                placeholder="₹ / month"
                className="w-28 px-3 py-2 text-sm"
                style={{ background: COLORS.surface, border: `1px solid ${COLORS.hairline}`, borderRadius: 8 }}
              />
            </div>
            <button
              onClick={setBudget}
              className="w-full py-3 text-sm font-medium mb-3"
              style={{ background: COLORS.ink, color: COLORS.parchment, borderRadius: 8 }}
            >
              Set budget
            </button>
            {budgetStatus && <p style={{ fontSize: 13, color: COLORS.muted, marginBottom: 16 }}>{budgetStatus}</p>}

            {budgetRows.length === 0 ? (
              <p style={{ fontSize: 13, color: COLORS.muted, fontStyle: "italic" }}>
                Set a budget above to track it against this month's spend.
              </p>
            ) : (
              <div className="space-y-3">
                {budgetRows.map((r) => {
                  const pct = Math.min((r.spent / r.limit) * 100, 100);
                  const over = r.spent > r.limit;
                  return (
                    <div key={r.category}>
                      <div className="flex justify-between text-xs mb-1">
                        <span style={{ color: COLORS.ink }}>{r.category}</span>
                        <span style={{ fontFamily: MONO, color: over ? COLORS.terracotta : COLORS.ink }}>
                          ₹{r.spent.toFixed(0)} / ₹{r.limit.toFixed(0)}
                        </span>
                      </div>
                      <div style={{ height: 6, background: COLORS.hairline, borderRadius: 3 }}>
                        <div style={{ height: 6, width: `${pct}%`, background: over ? COLORS.terracotta : COLORS.sage, borderRadius: 3 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
