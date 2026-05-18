import { ConfidenceProfile } from '../api';

interface Props {
  profile: ConfidenceProfile;
}

export default function ConfidenceBadge({ profile }: Props) {
  const scorePct = Math.round(profile.score * 100);
  const levelClass = scorePct >= 90 ? 'high' : scorePct >= 70 ? 'medium' : 'low';

  return (
    <div>
      <div className={`confidence-badge ${levelClass}`}>
        {scorePct >= 90 ? '\u{1F7E2}' : scorePct >= 70 ? '\u{1F7E1}' : '\u{1F534}'}
        Confidence: {scorePct}%
      </div>
      <div className="confidence-details">
        Open unknowns: {profile.open_unknowns} / {profile.total_unknowns} total |
        Validation ratio: {Math.round(profile.validation_ratio * 100)}%
      </div>
      {profile.fragility_flag && (
        <div className="fragile-warning">
          {'\u26A0'} Fragile: Specialist produced divergent assumptions at high temperature
        </div>
      )}
    </div>
  );
}
