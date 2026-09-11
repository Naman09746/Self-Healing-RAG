"use client";

import { useState, useRef, useEffect, useCallback } from "react";

/**
 * Checks whether a drag event contains external files (not text selection)
 */
function containsFiles(dataTransfer: DataTransfer | null): boolean {
  if (!dataTransfer) return false;
  const types = dataTransfer.types;
  if (!types || types.length === 0) return false;
  if (Array.isArray(types)) {
    return types.some((t) => t === "Files" || t === "application/x-moz-file" || t.toLowerCase().includes("file"));
  }
  if (typeof types.includes === "function") {
    return types.includes("Files") || types.includes("application/x-moz-file");
  }
  return Array.from(types).some((t) => t === "Files" || t === "application/x-moz-file" || t.toLowerCase().includes("file"));
}

export interface DragDropOptions {
  onDrop: (files: File[]) => void | Promise<void>;
  accept?: string[];
  multiple?: boolean;
  maxFiles?: number;
  maxSizeBytes?: number; // default 50 MB
  disabled?: boolean;
}

/**
 * Enterprise-grade full-page / container Drag & Drop hook
 * Zero flickering, cross-browser support (Chrome, Safari, Firefox, Edge),
 * Escape-key cancellation, and clean lifecycle tracking.
 */
export function useDragDrop({
  onDrop,
  accept,
  multiple = true,
  maxFiles = 10,
  maxSizeBytes = 50 * 1024 * 1024,
  disabled = false,
}: DragDropOptions) {
  const [isDragging, setIsDragging] = useState(false);
  const [isHoveringZone, setIsHoveringZone] = useState(false);
  const dragCounter = useRef(0);
  const onDropRef = useRef(onDrop);

  useEffect(() => {
    onDropRef.current = onDrop;
  }, [onDrop]);

  const filterFiles = useCallback(
    (fileList: FileList | File[]): File[] => {
      let files = Array.from(fileList).filter((f) => f && f.size > 0 && !f.name.startsWith("."));
      
      if (maxSizeBytes) {
        files = files.filter((f) => f.size <= maxSizeBytes);
      }
      if (!multiple) {
        files = files.slice(0, 1);
      }
      if (files.length > maxFiles) {
        files = files.slice(0, maxFiles);
      }
      return files;
    },
    [multiple, maxFiles, maxSizeBytes]
  );

  // Global window listeners to prevent browser default drop (opening file in tab)
  useEffect(() => {
    if (disabled) return;

    const handleWindowDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer && containsFiles(e.dataTransfer)) {
        e.dataTransfer.dropEffect = "copy";
      }
    };

    const handleWindowDrop = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current = 0;
      setIsDragging(false);
      setIsHoveringZone(false);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        dragCounter.current = 0;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    };

    window.addEventListener("dragover", handleWindowDragOver);
    window.addEventListener("drop", handleWindowDrop);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("dragover", handleWindowDragOver);
      window.removeEventListener("drop", handleWindowDrop);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [disabled]);

  const handleDragEnter = useCallback(
    (e: React.DragEvent) => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      if (e.dataTransfer && containsFiles(e.dataTransfer)) {
        e.dataTransfer.dropEffect = "copy";
        dragCounter.current += 1;
        setIsDragging(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      dragCounter.current -= 1;
      if (dragCounter.current <= 0) {
        dragCounter.current = 0;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    },
    [disabled]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      if (e.dataTransfer && containsFiles(e.dataTransfer)) {
        e.dataTransfer.dropEffect = "copy";
        if (!isDragging) {
          setIsDragging(true);
        }
      }
    },
    [disabled, isDragging]
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();

      dragCounter.current = 0;
      setIsDragging(false);
      setIsHoveringZone(false);

      let files: File[] = [];
      if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
        files = filterFiles(e.dataTransfer.files);
      } else if (e.dataTransfer?.items) {
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
    [disabled, filterFiles]
  );

  // Dedicated handlers for specific drop cards / zones
  const zoneDragHandlers = {
    onDragEnter: (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsHoveringZone(true);
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    },
    onDragLeave: (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsHoveringZone(false);
    },
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsHoveringZone(true);
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    },
    onDrop: handleDrop,
  };

  const containerDragHandlers = {
    onDragEnter: handleDragEnter,
    onDragLeave: handleDragLeave,
    onDragOver: handleDragOver,
    onDrop: handleDrop,
  };

  return {
    isDragging,
    isHoveringZone,
    dragHandlers: containerDragHandlers,
    zoneDragHandlers,
    filterFiles,
  };
}
