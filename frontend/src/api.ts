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

// Phase 1 types
export interface FileSpec {
  path: string;
  purpose: string;
  content_type: string;
}

export interface ComponentSpec {
  name: string;
  responsibility: string;
  depends_on: string[];
}

export interface APIRoute {
  method: string;
  path: string;
  description: string;
}

export interface TechPlan {
  plan_id: string;
  understanding_id: string;
  tech_stack: string[];
  file_tree: FileSpec[];
  components: ComponentSpec[];
  api_routes: APIRoute[];
  markdown_summary: string;
}

export interface BuildArtifact {
  build_id: string;
  plan_id: string;
  files_created: string[];
  files_modified: string[];
  docker_logs: string[];
  status: string;
}

export interface TestResult {
  test_name: string;
  status: string;
  error_message: string | null;
}

export interface TestReport {
  report_id: string;
  build_id: string;
  passed: number;
  failed: number;
  skipped: number;
  coverage_pct: number | null;
  details: TestResult[];
}

export interface TestPlan {
  plan_id: string;
  build_id: string;
  framework: string;
  test_files: FileSpec[];
  acceptance_criteria: string[];
}

// Phase 1 API methods
export async function createPlan(understandingId: string): Promise<{ plan: TechPlan; plan_id: string }> {
  const res = await fetch(`${API_BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ understanding_id: understandingId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function createBuild(planId: string): Promise<{ build: BuildArtifact }> {
  const res = await fetch(`${API_BASE}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function runTests(buildId: string): Promise<{ test_plan: TestPlan; test_report: TestReport }> {
  const res = await fetch(`${API_BASE}/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ build_id: buildId }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function commitBuild(buildId: string, message: string): Promise<{ commit_sha: string; success: boolean }> {
  const res = await fetch(`${API_BASE}/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ build_id: buildId, message }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
