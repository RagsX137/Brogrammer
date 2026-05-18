import { TechPlan } from '../api';

interface Props {
  plan: TechPlan;
  onApprove?: () => void;
  onRetry?: () => void;
  approved?: boolean;
}

export default function TechPlanView({ plan, onApprove, onRetry, approved }: Props) {
  const typeLabels: Record<string, string> = {
    code: '\u{1F4BB}',
    config: '\u{2699}\uFE0F',
    test: '\u{1F9EA}',
    doc: '\u{1F4DD}',
  };

  return (
    <div className="section">
      <h2>Tech Plan {approved && <span style={{ color: '#16a34a' }}>Approved</span>}</h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Tech Stack</h3>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {plan.tech_stack.map((t) => (
          <span key={t} className="tag tag-validated">{t}</span>
        ))}
      </div>

      <h3 style={{ fontSize: '1rem' }}>File Tree</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Purpose</th>
            <th style={{ textAlign: 'left', padding: '6px 8px' }}>Type</th>
          </tr>
        </thead>
        <tbody>
          {plan.file_tree.map((f, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{f.path}</td>
              <td style={{ padding: '4px 8px' }}>{f.purpose}</td>
              <td style={{ padding: '4px 8px' }}>{typeLabels[f.content_type] || f.content_type}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {plan.api_routes.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>API Routes</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Method</th>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Path</th>
                <th style={{ textAlign: 'left', padding: '6px 8px' }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {plan.api_routes.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '4px 8px' }}>
                    <span className={`tag ${r.method === 'GET' ? 'tag-validated' : 'tag-open'}`}>
                      {r.method}
                    </span>
                  </td>
                  <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{r.path}</td>
                  <td style={{ padding: '4px 8px' }}>{r.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Summary</h3>
      <div style={{ background: '#f9f9f9', padding: 12, borderRadius: 6, fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
        {plan.markdown_summary}
      </div>

      {!approved && onApprove && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={onApprove}>Approve Plan</button>
          {onRetry && <button className="btn" onClick={onRetry}>Retry</button>}
        </div>
      )}
    </div>
  );
}
