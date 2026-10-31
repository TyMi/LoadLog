/** Diagramme (serverseitig erzeugte SVGs) im Browser als SVG oder PNG speichern, ohne weitere Bibliothek. */

/** Breite und Höhe aus dem viewBox des SVG (Standardgröße, falls keine Angabe). */
export function svgSize(svg: string): { w: number; h: number } {
  const m = svg.match(/viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"/);
  return m ? { w: Number(m[1]), h: Number(m[2]) } : { w: 720, h: 320 };
}

/** Dateiname aus der Diagramm-Adresse: /api/charts/series/7/sequence.svg?… wird loadlog-series-7-sequence.<ext>. */
export function chartFileName(url: string, ext: "svg" | "png"): string {
  const path = url.split("?")[0].replace(/^\/api\/charts\//, "").replace(/\.svg$/, "");
  return `loadlog-${path.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "chart"}.${ext}`;
}

function download(blob: Blob, name: string): void {
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export function saveSvg(svg: string, name: string): void {
  download(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), name);
}

/** Zeichnet das SVG auf eine Leinwand (Hintergrund wie die Seite, damit helle Linien lesbar bleiben) und speichert sie als PNG. */
export async function savePng(svg: string, name: string, scale = 2, background = "#171e27"): Promise<void> {
  const { w, h } = svgSize(svg);
  const img = new Image();
  const src = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("SVG"));
      img.src = src;
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("PNG");
    download(blob, name);
  } finally {
    URL.revokeObjectURL(src);
  }
}
