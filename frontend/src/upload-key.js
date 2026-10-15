const keys = new WeakMap();

export function uploadKey(file) {
  if (!keys.has(file)) keys.set(file, crypto.randomUUID());
  return keys.get(file);
}
