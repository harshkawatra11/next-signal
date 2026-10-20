import { create } from "zustand";
import type { EvidenceItem } from "@/types/report";

interface DrawerState {
  open: boolean;
  item: EvidenceItem | null;
  related: EvidenceItem[];
  show: (item: EvidenceItem, related?: EvidenceItem[]) => void;
  close: () => void;
}

export const useEvidenceDrawer = create<DrawerState>((set) => ({
  open: false,
  item: null,
  related: [],
  show: (item, related = []) => set({ open: true, item, related }),
  close: () => set({ open: false }),
}));
