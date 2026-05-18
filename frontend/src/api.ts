const API_BASE = '/api';

export interface Assumption {
  id: string;
  statement: string;
  status: 'open' | 'validated' | 'invalidated';
  validated_by: string | null;
}

export interface Unknown {
  id: string;
  question: string;
  resolution: string | null;
  resolved_at: string | null;
}

export interface MandatoryCategories {
  accessibility: string[];
  performance: string[];
  security: string[];
  state_management: string[];
  persistence: string[];
}

export interface Understanding {
  id: string;
  goal: string;
  assumptions: Assumption[];
  unknowns: Unknown[];
  mandatory_categories: MandatoryCategories;
}

export interface SkepticCritique {
  critique_id: string;
  understanding_id: string;
  scenarios: string[];
  questions: string[];
  tool_evidence: string[];
}

export interface ConfidenceProfile {
  score: number;
  open_unknowns: number;
  total_unknowns: number;
  validation_ratio: number;
  fragility_flag: boolean;
}

export interface RunLoopResponse {
  understanding: Understanding;
  critique: SkepticCritique;
  confidence: ConfidenceProfile;
  critique_resolved: boolean;
}

export async function runLoop(goal: string): Promise<RunLoopResponse> {
  const res = await fetch(`${API_BASE}/run-loop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function resolveCritique(critiqueId: string, resolution: string) {
  const res = await fetch(`${API_BASE}/resolve-critique`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ critique_id: critiqueId, resolution }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getAuditEvents(limit = 50) {
  const res = await fetch(`${API_BASE}/audit/events?limit=${limit}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
