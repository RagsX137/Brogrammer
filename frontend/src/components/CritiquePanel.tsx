import { useState } from 'react';
import { SkepticCritique } from '../api';

interface Props {
  critique: SkepticCritique;
  resolved: boolean;
  onResolve: (critiqueId: string, resolution: string) => void;
}

export default function CritiquePanel({ critique, resolved, onResolve }: Props) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = () => {
    if (inputValue.trim()) {
      onResolve(critique.critique_id, inputValue.trim());
      setInputValue('');
      setActiveIndex(null);
    }
  };

  return (
    <div className="section">
      <h2>Skeptic Critique {resolved && <span style={{ color: '#16a34a' }}>{'\u2705'} Resolved</span>}</h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Failure Scenarios</h3>
      {critique.scenarios.length === 0 && <p style={{ color: '#999' }}>No scenarios identified</p>}
      {critique.scenarios.map((s, i) => (
        <div key={i} className="critique-item">{'\u26A0'} {s}</div>
      ))}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Questions for Resolution</h3>
      {critique.questions.length === 0 && <p style={{ color: '#999' }}>No questions</p>}
      {critique.questions.map((q, i) => (
        <div key={i} className="critique-item">
          <div>{'\u2753'} {q}</div>
          {!resolved && (
            <>
              <button className="resolve-btn" onClick={() => {
                setActiveIndex(activeIndex === i ? null : i);
                setInputValue('');
              }}>
                {activeIndex === i ? 'Cancel' : 'Resolve'}
              </button>
              {activeIndex === i && (
                <div style={{ marginTop: 8 }}>
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Your resolution..."
                    style={{ padding: '6px 10px', border: '1px solid #ccc', borderRadius: 4, width: '60%', marginRight: 8 }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSubmit();
                    }}
                  />
                  <button className="resolve-btn" onClick={() => handleSubmit()}>
                    Submit
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ))}

      {critique.tool_evidence.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Tool Evidence</h3>
          <ul style={{ paddingLeft: 20, fontSize: '0.9rem', color: '#666' }}>
            {critique.tool_evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}
