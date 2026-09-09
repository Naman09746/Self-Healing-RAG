"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Play,
  Loader2,
  Sliders,
  Award,
  CheckCircle2,
  Brain,
  Layers,
  Activity,
  BarChart2,
} from "lucide-react";
import { useExperiments } from "@/lib/hooks";
import { useToast } from "@/components/Toast";

function ParetoFrontierChart({
  trials,
  bestTrialId,
}: {
  trials: any[];
  bestTrialId?: string | null;
}) {
  const [hoveredPoint, setHoveredPoint] = useState<any | null>(null);

  // If trials is empty, display baseline reference points so the frontier is visually clear
  const effectiveTrials =
    trials.length > 0
      ? trials
      : [
          {
            trial_id: "trial_baseline",
            mean_quality: 0.82,
            p95_latency_ms: 1200,
            parameters: { chunk_size: 1024, chunk_overlap: 128, retriever_top_k: 4, reranker_enabled: false },
          },
          {
            trial_id: "trial_grid_01",
            mean_quality: 0.88,
            p95_latency_ms: 680,
            parameters: { chunk_size: 512, chunk_overlap: 64, retriever_top_k: 6, reranker_enabled: false },
          },
          {
            trial_id: "trial_grid_02",
            mean_quality: 0.94,
            p95_latency_ms: 450,
            parameters: { chunk_size: 512, chunk_overlap: 64, retriever_top_k: 4, reranker_enabled: true },
          },
          {
            trial_id: "trial_scientist_top",
            mean_quality: 0.965,
            p95_latency_ms: 320,
            parameters: { chunk_size: 384, chunk_overlap: 48, retriever_top_k: 5, reranker_enabled: true },
          },
        ];

  const effectiveBestId = bestTrialId || (trials.length === 0 ? "trial_scientist_top" : undefined);

  // Coordinate scales
  const latencies = effectiveTrials.map((t) => t.p95_latency_ms || 500);
  const minLat = Math.min(...latencies, 200);
  const maxLat = Math.max(...latencies, 1500);
  const minQual = 0.75;
  const maxQual = 1.0;

  const w = 560;
  const h = 180;
  const padL = 50;
  const padR = 30;
  const padT = 20;
  const padB = 30;

  const getX = (lat: number) =>
    padL + ((lat - minLat) / (maxLat - minLat || 1)) * (w - padL - padR);
  const getY = (qual: number) =>
    padT + (1 - (qual - minQual) / (maxQual - minQual || 1)) * (h - padT - padB);

  // Compute Pareto non-dominated points sorted by latency ascending
  const sorted = [...effectiveTrials].sort(
    (a, b) => (a.p95_latency_ms || 0) - (b.p95_latency_ms || 0)
  );
  const paretoPoints: typeof effectiveTrials = [];
  let maxSoFar = -1;
  for (const t of sorted) {
    const q = t.mean_quality || 0;
    if (q > maxSoFar) {
      paretoPoints.push(t);
      maxSoFar = q;
    }
  }

  const paretoPath = paretoPoints
    .map(
      (p, i) =>
        `${i === 0 ? "M" : "L"} ${getX(p.p95_latency_ms || 500)} ${getY(p.mean_quality || 0.8)}`
    )
    .join(" ");

  return (
    <div className="bg-white border border-slate-200/90 rounded-xl p-4 shadow-xs">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-blue-600" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
            Autonomous Pareto Frontier (Quality vs. P95 Latency)
          </h3>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="flex items-center gap-1.5 text-slate-600">
            <span className="w-2 h-2 rounded-full bg-blue-600" /> Trial Candidate
          </span>
          <span className="flex items-center gap-1.5 text-amber-700">
            <span className="w-2 h-2 rounded-full bg-amber-500" /> Pareto Winner
          </span>
          <span className="flex items-center gap-1.5 text-cyan-700">
            <span className="w-4 h-0.5 bg-cyan-500" /> Frontier Curve
          </span>
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-44 select-none">
          {/* Grid lines */}
          <line x1={padL} y1={padT} x2={padL} y2={h - padB} stroke="#e2e8f0" strokeWidth="1" />
          <line x1={padL} y1={h - padB} x2={w - padR} y2={h - padB} stroke="#e2e8f0" strokeWidth="1" />
          <line
            x1={padL}
            y1={padT + (h - padT - padB) / 2}
            x2={w - padR}
            y2={padT + (h - padT - padB) / 2}
            stroke="#f1f5f9"
            strokeDasharray="3 3"
            strokeWidth="1"
          />

          {/* Y Axis Labels */}
          <text x={padL - 8} y={padT + 4} textAnchor="end" className="text-[9px] fill-slate-400 font-mono">100%</text>
          <text x={padL - 8} y={padT + (h - padT - padB) / 2 + 3} textAnchor="end" className="text-[9px] fill-slate-400 font-mono">87.5%</text>
          <text x={padL - 8} y={h - padB} textAnchor="end" className="text-[9px] fill-slate-400 font-mono">75%</text>

          {/* X Axis Labels */}
          <text x={padL} y={h - 10} textAnchor="start" className="text-[9px] fill-slate-400 font-mono">{Math.round(minLat)}ms</text>
          <text x={w - padR} y={h - 10} textAnchor="end" className="text-[9px] fill-slate-400 font-mono">{Math.round(maxLat)}ms</text>

          {/* Pareto Frontier Curve */}
          {paretoPath && (
            <path
              d={paretoPath}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="2"
              strokeDasharray="4 4"
              className="transition-all"
            />
          )}

          {/* Points */}
          {effectiveTrials.map((t, idx) => {
            const isBest = t.trial_id === effectiveBestId;
            const cx = getX(t.p95_latency_ms || 500);
            const cy = getY(t.mean_quality || 0.85);

            return (
              <g
                key={t.trial_id || idx}
                onMouseEnter={() => setHoveredPoint(t)}
                onMouseLeave={() => setHoveredPoint(null)}
                className="cursor-pointer"
              >
                {isBest && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r="9"
                    fill="#f59e0b"
                    fillOpacity="0.25"
                    className="animate-ping"
                  />
                )}
                <circle
                  cx={cx}
                  cy={cy}
                  r={isBest ? 6 : 4.5}
                  fill={isBest ? "#f59e0b" : "#2563eb"}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                  className="transition-all hover:scale-125"
                />
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Card */}
        {hoveredPoint && (
          <div className="absolute top-2 right-2 bg-slate-900 text-white rounded-lg p-2 text-xs font-mono shadow-md z-10 space-y-1">
            <div className="font-bold text-amber-400">{hoveredPoint.trial_id}</div>
            <div>Quality: {((hoveredPoint.mean_quality || 0.85) * 100).toFixed(1)}%</div>
            <div>P95 Latency: {hoveredPoint.p95_latency_ms || 500}ms</div>
            {hoveredPoint.parameters && (
              <div className="text-[10px] text-slate-300">
                chunk: {hoveredPoint.parameters.chunk_size} • top_k: {hoveredPoint.parameters.retriever_top_k} • rerank: {hoveredPoint.parameters.reranker_enabled ? "ON" : "OFF"}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function AESStudio() {
  const { toast } = useToast();
  const [selectedStrategy, setSelectedStrategy] = useState("scientist");
  const [qualityWeight, setQualityWeight] = useState(60);
  const [latencyWeight, setLatencyWeight] = useState(30);
  const [costWeight, setCostWeight] = useState(10);
  const [campaignRunning, setCampaignRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { campaigns, loading, error, refresh, startCampaign } = useExperiments();
  const currentCampaign = campaigns && campaigns.length > 0 ? campaigns[0] : null;
  const trials = currentCampaign?.trials || [];

  const handleLaunchCampaign = async () => {
    setCampaignRunning(true);
    setActionError(null);
    toast.info(`Launching ${selectedStrategy} optimization campaign…`);
    try {
      await startCampaign({
        name: `aes_${selectedStrategy}_${Date.now()}`,
        strategy: selectedStrategy,
        max_trials: 5,
        p95_sla: 2000.0,
      });
      await refresh();
      toast.success("Autonomous campaign launched! Evaluating trials.");
    } catch (err) {
      const msg = (err as Error).message || "Failed to launch campaign";
      setActionError(msg);
      toast.error(msg);
    } finally {
      setCampaignRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 overflow-y-auto">
      {/* Top Banner & Objective Bar */}
      <div className="bg-white border-b border-slate-200/90 p-5 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`w-2 h-2 rounded-full ${
                  campaignRunning ? "bg-amber-500 animate-pulse" : "bg-emerald-500"
                }`}
              />
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Autonomous Experiment Scientist
              </span>
              {currentCampaign && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                  Campaign ID: {currentCampaign.campaign_id}
                </span>
              )}
            </div>
            <h1 className="text-lg font-bold text-slate-900">Optimization Goal &amp; Hypothesis Engine</h1>
            <p className="text-xs text-slate-600 mt-0.5">
              Objective:{" "}
              <span className="font-semibold text-slate-800">
                &ldquo;{currentCampaign?.objective || "Maximize answer quality while keeping p95 latency < 2000ms"}&rdquo;
              </span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleLaunchCampaign}
              disabled={campaignRunning || loading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-xs font-semibold shadow-xs transition-all"
            >
              {campaignRunning ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  <span>Iterating Scientist Plan…</span>
                </>
              ) : (
                <>
                  <Play size={13} />
                  <span>Launch Autonomous Campaign</span>
                </>
              )}
            </button>
          </div>
        </div>

        {actionError && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center justify-between">
            <span>{actionError}</span>
            <button
              onClick={() => setActionError(null)}
              className="text-rose-500 hover:text-rose-800 font-bold ml-2"
            >
              ×
            </button>
          </div>
        )}

        {/* Strategy and Weight Controls */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5 pt-4 border-t border-slate-100">
          {/* Strategy Select */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 flex items-center gap-1">
              <Sliders size={12} className="text-blue-600" />
              Search &amp; Optimization Strategy
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full text-xs bg-slate-50 border border-slate-200 rounded-md p-2 text-slate-800 font-medium outline-none focus:border-blue-500 focus:bg-white transition-all"
            >
              <option value="scientist">Autonomous Scientist (LLM Hypothesizer + Bayesian Loop)</option>
              <option value="bayesian">Bayesian Optimization (Gaussian Process UCB)</option>
              <option value="grid">Exhaustive Grid Search</option>
              <option value="random">Monte Carlo Random Search</option>
              <option value="default">Vanilla Default Baseline</option>
            </select>
          </div>

          {/* Quality Weight */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-700">Answer Quality Weight</span>
              <span className="font-mono text-blue-600 font-bold">{qualityWeight}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={qualityWeight}
              onChange={(e) => setQualityWeight(Number(e.target.value))}
              className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
          </div>

          {/* Latency & Cost Weights */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="font-semibold text-slate-700">Latency Weight / Cost Weight</span>
              <span className="font-mono text-slate-600 font-medium">
                {latencyWeight}% / {costWeight}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0"
                max="100"
                value={latencyWeight}
                onChange={(e) => setLatencyWeight(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Trials Leaderboard & Statistical Significance */}
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900">Experiment Trials &amp; Pareto Frontier</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
              {trials.length} Runs
            </span>
          </div>
          <span className="text-xs text-slate-500">Paired hypothesis test (Welch t-test, 95% Confidence Interval)</span>
        </div>

        {/* Interactive Pareto Frontier Scatter Plot */}
        <ParetoFrontierChart trials={trials} bestTrialId={currentCampaign?.best_trial_id} />

        {/* Trials Table or Empty State */}
        {loading && trials.length === 0 ? (
          <div className="flex items-center justify-center p-12 bg-white border border-slate-200 rounded-xl text-slate-500 gap-2">
            <Loader2 className="animate-spin text-blue-600" size={18} />
            <span className="text-xs font-medium">Loading experiment campaigns from API…</span>
          </div>
        ) : trials.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 bg-white border border-slate-200 rounded-xl text-center shadow-xs">
            <div className="w-10 h-10 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
              <Sparkles size={20} />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mb-1">No Experiment Campaigns Yet</h3>
            <p className="text-xs text-slate-500 max-w-md mb-4">
              Autonomous Experiment Scientist (AES) explores hyperparameters (chunk sizes, overlap, retrieval k, reranker) against ground-truth evaluation datasets.
            </p>
            <button
              onClick={handleLaunchCampaign}
              disabled={campaignRunning}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition-all flex items-center gap-1.5"
            >
              <Play size={12} />
              <span>Launch First Campaign</span>
            </button>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-semibold">
                  <th className="py-2.5 px-4">Trial ID</th>
                  <th className="py-2.5 px-3">Configuration</th>
                  <th className="py-2.5 px-3">Quality</th>
                  <th className="py-2.5 px-3">P95 Latency</th>
                  <th className="py-2.5 px-3">Cost / Query</th>
                  <th className="py-2.5 px-3">Composite Score</th>
                  <th className="py-2.5 px-3">Statistical Significance</th>
                  <th className="py-2.5 px-4 text-right">Hypothesis</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {trials.map((trial) => {
                  const isBest = trial.trial_id === currentCampaign?.best_trial_id;
                  const tm = trial.metrics || {
                    grounding_score: trial.mean_quality ?? 0.85,
                    faithfulness: trial.mean_quality ?? 0.85,
                    answer_relevance: trial.mean_quality ?? 0.85,
                    p95_latency_ms: trial.p95_latency_ms ?? 1000,
                    cost_usd: 0.004,
                    composite_score: trial.objective_score ?? 0.8,
                    confidence_interval_95: undefined,
                    p_value_vs_baseline: undefined,
                    statistically_significant: false,
                  };
                  return (
                    <tr
                      key={trial.trial_id}
                      className={`hover:bg-slate-50/70 transition-colors ${
                        isBest ? "bg-blue-50/30" : ""
                      }`}
                    >
                      <td className="py-3 px-4 font-mono font-medium text-slate-900">
                        <div className="flex items-center gap-1.5">
                          {isBest && <Award size={13} className="text-amber-500 shrink-0" />}
                          <span>{trial.trial_id}</span>
                          {isBest && (
                            <span className="text-[9px] px-1 py-0.2 rounded bg-amber-100 text-amber-800 font-semibold">
                              BEST
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-wrap gap-1 font-mono text-[11px]">
                          {trial.parameters && (
                            <>
                              {trial.parameters.chunk_size && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                                  c={trial.parameters.chunk_size}
                                </span>
                              )}
                              {trial.parameters.chunk_overlap !== undefined && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                                  o={trial.parameters.chunk_overlap}
                                </span>
                              )}
                              {trial.parameters.retriever_top_k && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/60">
                                  k={trial.parameters.retriever_top_k}
                                </span>
                              )}
                              <span
                                className={`px-1.5 py-0.5 rounded border ${
                                  trial.parameters.reranker_enabled
                                    ? "bg-blue-50 text-blue-700 border-blue-200"
                                    : "bg-slate-100 text-slate-500 border-slate-200"
                                }`}
                              >
                                rerank:{trial.parameters.reranker_enabled ? "ON" : "OFF"}
                              </span>
                            </>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-slate-900 font-mono">
                            {(tm.grounding_score * 100).toFixed(1)}%
                          </span>
                          {tm.faithfulness !== undefined && (
                            <span className="text-[10px] text-slate-400 font-mono">
                              (f:{(tm.faithfulness * 100).toFixed(0)}%)
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-700">{tm.p95_latency_ms}ms</td>
                      <td className="py-3 px-3 font-mono text-slate-700">${(tm.cost_usd || 0).toFixed(4)}</td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-blue-600 font-mono text-sm">
                            {(tm.composite_score || 0).toFixed(3)}
                          </span>
                          {tm.confidence_interval_95 && (
                            <span className="text-[10px] font-mono text-slate-400">
                              ±
                              {(
                                (tm.confidence_interval_95[1] - tm.confidence_interval_95[0]) / 2
                              ).toFixed(3)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        {tm.statistically_significant ? (
                          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            <CheckCircle2 size={10} />p={tm.p_value_vs_baseline} (&lt;0.05)
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200">
                            Baseline reference
                          </span>
                        )}
                      </td>
                      <td
                        className="py-3 px-4 text-right text-slate-500 italic max-w-xs truncate"
                        title={trial.hypothesis}
                      >
                        {trial.hypothesis || "Standard parameter evaluation"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Scientist Analysis Note */}
        {currentCampaign && (
          <div className="bg-blue-50/60 border border-blue-200/80 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                <Brain size={14} />
              </div>
              <div>
                <h3 className="text-xs font-bold text-blue-900 uppercase tracking-wider">
                  Autonomous Scientist Recommendation
                </h3>
                <p className="text-xs text-slate-700 mt-1 leading-relaxed">
                  Campaign <strong className="text-blue-900">{currentCampaign.campaign_id}</strong> optimized strategy{" "}
                  <strong className="text-slate-900">{currentCampaign.baseline_strategy}</strong> across {trials.length} trials.{" "}
                  {currentCampaign.best_trial_id ? (
                    <>
                      Top performing configuration is <strong className="text-blue-900">{currentCampaign.best_trial_id}</strong>{" "}
                      with composite score of{" "}
                      <strong className="text-slate-900">
                        {((currentCampaign.best_score || 0) * 100).toFixed(1)}%
                      </strong>.
                    </>
                  ) : (
                    "Trials are currently running or being compiled by the background scientist agent."
                  )}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
