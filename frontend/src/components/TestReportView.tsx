import { useState } from 'react';
import { TestReport } from '../api';

interface Props {
  report: TestReport;
  onApprove?: () => void;
  onRetry?: () => void;
  approved?: boolean;
}

export default function TestReportView({ report, onApprove, onRetry, approved }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const statusColor = report.failed === 0 ? '#16a34a' : '#dc2626';

  return (
    <div className="section">
      <h2>
        Test Report
        {!approved && (
          <span style={{ color: statusColor, marginLeft: 8 }}>
            {report.failed === 0 ? 'All Passing' : `${report.failed} Failed`}
          </span>
        )}
        {approved && <span style={{ color: '#16a34a', marginLeft: 8 }}>Approved</span>}
      </h2>

      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <div className="stat-box" style={report.passed > 0 ? { borderColor: '#16a34a' } : {}}>
          <span className="stat-value" style={{ color: '#16a34a' }}>{report.passed}</span>
          <span className="stat-label">Passed</span>
        </div>
        <div className="stat-box" style={report.failed > 0 ? { borderColor: '#dc2626' } : {}}>
          <span className="stat-value" style={{ color: '#dc2626' }}>{report.failed}</span>
          <span className="stat-label">Failed</span>
        </div>
        <div className="stat-box">
          <span className="stat-value" style={{ color: '#666' }}>{report.skipped}</span>
          <span className="stat-label">Skipped</span>
        </div>
        {report.coverage_pct !== null && (
          <div className="stat-box">
            <span className="stat-value">{report.coverage_pct}%</span>
            <span className="stat-label">Coverage</span>
          </div>
        )}
      </div>

      {report.details.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Details</h3>
          {report.details.map((d, i) => (
            <div key={i} className="test-detail-item">
              <span
                className={`tag ${d.status === 'passed' ? 'tag-validated' : 'tag-open'}`}
                onClick={() => setExpanded(expanded === i ? null : i)}
                style={{ cursor: d.error_message ? 'pointer' : 'default' }}
              >
                {d.status === 'passed' ? 'PASS' : d.status === 'failed' ? 'FAIL' : 'SKIP'} {d.status}
              </span>
              <span style={{ fontSize: '0.9rem' }}>{d.test_name}</span>
              {expanded === i && d.error_message && (
                <div className="error-detail">{d.error_message}</div>
              )}
            </div>
          ))}
        </>
      )}

      {!approved && onApprove && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={onApprove}>Approve Build</button>
          {onRetry && <button className="btn" onClick={onRetry}>Retry Build</button>}
        </div>
      )}
    </div>
  );
}
