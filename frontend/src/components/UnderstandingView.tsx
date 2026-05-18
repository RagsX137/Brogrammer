import { Understanding } from '../api';

interface Props {
  understanding: Understanding;
}

function statusTag(status: string) {
  const labels: Record<string, string> = {
    open: '\u{1F534} Open',
    validated: '\u{1F7E2} Validated',
    invalidated: '\u{1F534} Invalidated',
  };
  return labels[status] || status;
}

function statusClass(status: string) {
  const classes: Record<string, string> = {
    open: 'tag-open',
    validated: 'tag-validated',
    invalidated: 'tag-invalidated',
  };
  return classes[status] || '';
}

export default function UnderstandingView({ understanding }: Props) {
  return (
    <div className="section">
      <h2>Understanding</h2>
      <p><strong>Goal:</strong> {understanding.goal}</p>

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Assumptions</h3>
      {understanding.assumptions.length === 0 && <p style={{ color: '#999' }}>None identified</p>}
      {understanding.assumptions.map((a) => (
        <div key={a.id} className="assumption-item">
          <span className={`tag ${statusClass(a.status)}`}>{statusTag(a.status)}</span>
          <span>{a.statement}</span>
          {a.validated_by && <span style={{ fontSize: '0.8rem', color: '#666' }}>(by {a.validated_by})</span>}
        </div>
      ))}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Unknowns</h3>
      {understanding.unknowns.length === 0 && <p style={{ color: '#999' }}>None identified</p>}
      <ul style={{ paddingLeft: 20 }}>
        {understanding.unknowns.map((u) => (
          <li key={u.id}>
            {u.question}
            {u.resolution && <span style={{ color: '#16a34a' }}> \u2192 {u.resolution}</span>}
          </li>
        ))}
      </ul>

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Mandatory Categories</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
        <tbody>
          {(['accessibility', 'performance', 'security', 'state_management', 'persistence'] as const).map((cat) => (
            <tr key={cat}>
              <td style={{ padding: '4px 8px', fontWeight: 600, borderBottom: '1px solid #f0f0f0' }}>
                {cat.replace('_', ' ')}
              </td>
              <td style={{ padding: '4px 8px', borderBottom: '1px solid #f0f0f0' }}>
                {understanding.mandatory_categories[cat].length > 0
                  ? understanding.mandatory_categories[cat].join(', ')
                  : <span style={{ color: '#dc2626' }}>{'\u26A0'} Empty</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
