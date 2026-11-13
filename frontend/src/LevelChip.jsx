// Small coloured label: HIGH, MEDIUM or LOW. The word is always shown, so colour is never the only signal.
export default function LevelChip({ level }) {
  return <span className={'chip ' + level}>{level.toUpperCase()}</span>;
}
