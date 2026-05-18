import { useState } from 'react';
import { runLoop, resolveCritique, RunLoopResponse } from './api';
import UnderstandingView from './components/UnderstandingView';
import CritiquePanel from './components/CritiquePanel';
import ConfidenceBadge from './components/ConfidenceBadge';

function App() {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RunLoopResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runLoop(goal.trim());
      setResult(data);
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

  return (
    <div className="app">
      <h1>Brogrammer — Phase 0</h1>

      <div className="goal-input">
        <input
          type="text"
          placeholder="Describe what you want to build..."
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRun()}
        />
        <button onClick={handleRun} disabled={loading}>
          {loading ? 'Running...' : 'Run Loop'}
        </button>
      </div>

      {error && <div className="section" style={{ color: '#dc2626' }}>{error}</div>}

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
          </div>
        </>
      )}
    </div>
  );
}

export default App;
