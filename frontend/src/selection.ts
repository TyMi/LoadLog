export const togglePick = (picked: number[], id: number): number[] => (picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);

/** Alle auswählen; sind schon alle gewählt, die Auswahl leeren. */
export const toggleAll = (picked: number[], all: number[]): number[] => (all.length > 0 && all.every((i) => picked.includes(i)) ? [] : [...all]);
