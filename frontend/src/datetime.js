export function localDateTime(value) {
  if (!value) return '';
  const date=new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
