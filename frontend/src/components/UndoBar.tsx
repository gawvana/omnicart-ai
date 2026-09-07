/**
 * OmniCart AI — UndoBar
 * Thin wrapper / helper around Toast for undo actions.
 */

import React from "react";
import Toast from "./Toast";
import type { ToastData } from "../types";

interface UndoBarProps {
  toast: ToastData | null;
  onDismiss: () => void;
  onUndo: () => void;
}

export const UndoBar: React.FC<UndoBarProps> = ({ toast, onDismiss, onUndo }) => {
  return <Toast toast={toast} onDismiss={onDismiss} onAction={onUndo} />;
};

export default UndoBar;
