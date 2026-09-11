"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface UseDragDropOptions {
  onDrop: (files: File[]) => void | Promise<void>;
  accept?: string[]; // e.g. [".pdf", ".png"]
  multiple?: boolean;
  maxFiles?: number;
}

export function useDragDrop({ onDrop, accept, multiple = true, maxFiles = 10 }: UseDragDropOptions) {
  const [isDragging, setIsDragging] = useState(false);
  const [isDragOverZone, setIsDragOverZone] = useState(false);
  const dragCounter = useRef(0);

  // Keep onDrop ref to avoid re-binding window listeners
  const onDropRef = useRef(onDrop);
  useEffect(() => {
    onDropRef.current = onDrop;
  }, [onDrop]);

  const isValidFile = useCallback(
    (file: File) => {
      if (!accept || accept.length === 0) return true;
      const ext = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
      const mime = file.type.toLowerCase();
      // Accept if ext matches or mime matches (e.g. image/*)
      return accept.some((a) => {
        const acc = a.toLowerCase().trim();
        if (acc.startsWith(".")) return ext === acc;
        if (acc.endsWith("/*")) return mime.startsWith(acc.replace("/*", "/"));
        return mime === acc || ext === acc;
      });
    },
    [accept]
  );

  const filterFiles = useCallback(
    (fileList: FileList | File[]) => {
      let files = Array.from(fileList).filter((f) => f.size > 0 && !f.name.startsWith("."));
      if (accept) {
        // Warn but don't block — backend handles unknown via text fallback
        // Just filter out empty, keep all for backend to try
      }
      if (!multiple) files = files.slice(0, 1);
      if (files.length > maxFiles) files = files.slice(0, maxFiles);
      return files;
    },
    [multiple, maxFiles, accept]
  );

  // Window-level to kill browser dark default overlay
  useEffect(() => {
    const onWindowDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    };
    const onWindowDrop = (e: DragEvent) => {
      e.preventDefault();
    };
    window.addEventListener("dragover", onWindowDragOver);
    window.addEventListener("drop", onWindowDrop);
    return () => {
      window.removeEventListener("dragover", onWindowDragOver);
      window.removeEventListener("drop", onWindowDrop);
    };
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    dragCounter.current += 1;
    // Only set if files are being dragged
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
      setIsDragOverZone(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
      setIsDragOverZone(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    // Ensure state stays true while over zone
    if (!isDragOverZone && e.dataTransfer.types.includes("Files")) {
      setIsDragOverZone(true);
      setIsDragging(true);
    }
  }, [isDragOverZone]);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setIsDragging(false);
      setIsDragOverZone(false);

      // Prefer files, fallback to items (Safari/Firefox edge)
      let files: File[] = [];
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        files = filterFiles(e.dataTransfer.files);
      } else if (e.dataTransfer.items) {
        const items = Array.from(e.dataTransfer.items)
          .filter((it) => it.kind === "file")
          .map((it) => it.getAsFile())
          .filter(Boolean) as File[];
        files = filterFiles(items);
      }
      if (files.length > 0) {
        await onDropRef.current(files);
      }
    },
    [filterFiles]
  );

  const dragHandlers = {
    onDragEnter: handleDragEnter,
    onDragLeave: handleDragLeave,
    onDragOver: handleDragOver,
    onDrop: handleDrop,
  };

  return { isDragging, isDragOverZone, dragHandlers, filterFiles };
}
