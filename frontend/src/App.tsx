import { useState } from 'react';
import { runLoop, resolveCritique, createPlan, createBuild, runTests, commitBuild, RunLoopResponse, TechPlan, BuildArtifact, TestReport } from './api';
import UnderstandingView from './components/UnderstandingView';
import CritiquePanel from './components/CritiquePanel';
import ConfidenceBadge from './components/ConfidenceBadge';
import TechPlanView from './components/TechPlanView';
import BuildView from './components/BuildView';
import TestReportView from './components/TestReportView';

type GateStep = 'goal' | 'understanding' | 'design' | 'build' | 'test' | 'commit' | 'done';

function App() {
  const [step, setStep] = useState<GateStep>('goal');
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunLoopResponse | null>(null);
  const [plan, setPlan] = useState<TechPlan | null>(null);
  const [build, setBuild] = useState<BuildArtifact | null>(null);
  const [testReport, setTestReport] = useState<TestReport | null>(null);
  const [commitSha, setCommitSha] = useState<string | null>(null);

  const handleRun = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runLoop(goal.trim());
      setResult(data);
      setStep('understanding');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (critiqueId: string, resolution: string) => {
    try {
      await resolveCritique(critiqueId, resolution);
      setResult((prev) => prev ? { ...prev, critique_resolved: true } : prev);
    } catch (e) {
      console.error('Resolve failed', e);
    }
  };

  const handlePlan = async () => {
    if (!result) return;
    setLoading(true);
    setError(null);
    try {
      const data = await createPlan(result.understanding.id);
      setPlan(data.plan);
      setStep('design');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Plan failed');
    } finally {
      setLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const data = await createBuild(plan.plan_id);
      setBuild(data.build);
      setStep('build');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Build failed');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!build) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runTests(build.build_id);
      setTestReport(data.test_report);
      setStep('test');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Tests failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!build) return;
    const msg = `Brogrammer build ${build.build_id.slice(0, 8)}`;
    setLoading(true);
    setError(null);
    try {
      const data = await commitBuild(build.build_id, msg);
      if (data.success) {
        setCommitSha(data.commit_sha);
        setStep('done');
      } else {
        setError('Git commit failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Commit failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep('goal');
    setResult(null);
    setPlan(null);
    setBuild(null);
    setTestReport(null);
    setCommitSha(null);
    setError(null);
  };

  const gateSteps: GateStep[] = ['goal', 'understanding', 'design', 'build', 'test', 'commit', 'done'];
  const stepIndex = gateSteps.indexOf(step);

  return (
    <div className="app">
      <h1>Brogrammer - Gate Flow</h1>

      <div className="gate-steps">
        {gateSteps.map((s, i) => (
          <div key={s} className={`gate-step ${step === s ? 'active' : ''} ${i < stepIndex ? 'completed' : ''}`}>
            <div className="gate-step-number">{i < stepIndex ? '\u2713' : i + 1}</div>
            <div className="gate-step-label">{s.charAt(0).toUpperCase() + s.slice(1)}</div>
          </div>
        ))}
      </div>

      <div className="goal-input">
        <input
          type="text"
          placeholder="Describe what you want to build..."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRun()}
          disabled={step !== 'goal'}
        />
        <button onClick={handleRun} disabled={loading || step !== 'goal'}>
          {loading ? 'Running...' : 'Start'}
        </button>
      </div>

      {error && <div className="section" style={{ color: '#dc2626' }}>Error: {error}</div>}

      {result && (
        <>
          <UnderstandingView understanding={result.understanding} />
          <CritiquePanel
            critique={result.critique}
            resolved={result.critique_resolved}
            onResolve={handleResolve}
          />
          <div className="section">
            <ConfidenceBadge profile={result.confidence} />
            {result.critique_resolved && step === 'understanding' && (
              <button className="btn btn-primary" onClick={handlePlan} style={{ marginTop: 12 }} disabled={loading}>
                {loading ? 'Planning...' : 'Proceed to Design Gate'}
              </button>
            )}
          </div>
        </>
      )}

      {plan && (
        <TechPlanView
          plan={plan}
          onApprove={() => { handleBuild(); }}
          onRetry={handlePlan}
          approved={step !== 'design'}
        />
      )}

      {build && (
        <BuildView build={build} loading={loading && step === 'build'} />
      )}

      {build && step === 'build' && !loading && (
        <div className="section">
          <button className="btn btn-primary" onClick={handleTest} disabled={loading}>
            {loading ? 'Testing...' : 'Proceed to Test Gate'}
          </button>
        </div>
      )}

      {testReport && (
        <TestReportView
          report={testReport}
          onApprove={handleCommit}
          onRetry={handleBuild}
          approved={step !== 'test'}
        />
      )}

      {step === 'commit' && !loading && (
        <div className="section">
          <p style={{ marginBottom: 8 }}>Ready to commit to Git?</p>
          <button className="btn btn-primary" onClick={handleCommit}>Commit Build</button>
        </div>
      )}

      {step === 'done' && (
        <div className="section">
          <h2>Phase Complete</h2>
          {commitSha && <p>Committed: <code>{commitSha}</code></p>}
          <button className="btn" onClick={handleReset} style={{ marginTop: 8 }}>Start New</button>
        </div>
      )}
    </div>
  );
}

export default App;
