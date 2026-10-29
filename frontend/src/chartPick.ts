export interface TrackLine {
  shot: number;
  label: string;
  points: [number, number][]; // SVG-Koordinaten
  vals: string[]; // Anzeigetext je Punkt
}
export interface Hit {
  shot: number;
  label: string;
  val: string;
  x: number;
  y: number;
  dist: number;
}

/** Messpunkt aller Linien, der der Position (x, y) am nächsten liegt; null, wenn keiner innerhalb von maxDist liegt. */
export function nearestPoint(lines: TrackLine[], x: number, y: number, maxDist = 30): Hit | null {
  let best: Hit | null = null;
  for (const l of lines) {
    l.points.forEach(([px, py], i) => {
      const dist = Math.hypot(px - x, py - y);
      if (!best || dist < best.dist) best = { shot: l.shot, label: l.label, val: l.vals[i] ?? "", x: px, y: py, dist };
    });
  }
  const hit = best as Hit | null;
  return hit && hit.dist <= maxDist ? hit : null;
}

export function parsePoints(attr: string): [number, number][] {
  return attr.trim().split(/\s+/).filter(Boolean).map((p) => {
    const [x, y] = p.split(",").map(Number);
    return [x, y];
  });
}
