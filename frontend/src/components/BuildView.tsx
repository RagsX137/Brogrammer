import { BuildArtifact } from '../api';

interface Props {
  build: BuildArtifact;
  loading?: boolean;
}

export default function BuildView({ build, loading }: Props) {
  const statusColor = build.status === 'success' ? '#16a34a' : '#dc2626';

  return (
    <div className="section">
      <h2>
        Build Artifact
        {!loading && (
          <span style={{ color: statusColor, marginLeft: 8 }}>
            {build.status === 'success' ? 'Success' : 'Failed'}
          </span>
        )}
        {loading && <span style={{ color: '#ca8a04', marginLeft: 8 }}>Building...</span>}
      </h2>

      <h3 style={{ marginTop: 8, fontSize: '1rem' }}>Files Created</h3>
      {build.files_created.length === 0 && <p style={{ color: '#999' }}>None</p>}
      <ul style={{ paddingLeft: 20 }}>
        {build.files_created.map((f, i) => (
          <li key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>+ {f}</li>
        ))}
      </ul>

      {build.files_modified.length > 0 && (
        <>
          <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Files Modified</h3>
          <ul style={{ paddingLeft: 20 }}>
            {build.files_modified.map((f, i) => (
              <li key={i} style={{ fontFamily: 'monospace', fontSize: '0.9rem', color: '#ca8a04' }}>+ {f}</li>
            ))}
          </ul>
        </>
      )}

      <h3 style={{ marginTop: 12, fontSize: '1rem' }}>Docker Logs</h3>
      <div className="log-panel">
        {build.docker_logs.map((line, i) => (
          <div key={i} className="log-line">{line}</div>
        ))}
      </div>
    </div>
  );
}
