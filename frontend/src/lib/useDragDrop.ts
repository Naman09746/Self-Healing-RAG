"use client";

import { useState, useRef, useEffect, useCallback } from "react";

/**
 * Checks whether a drag event contains external files (not internal text drag)
 */
function containsFiles(dataTransfer: DataTransfer | null): boolean {
  if (!dataTransfer) return false;
  const types = dataTransfer.types;
  if (!types || types.length === 0) return false;
  if (Array.isArray(types)) {
    return types.some(
      (t) => t === "Files" || t === "application/x-moz-file" || t.toLowerCase().includes("file")
    );
  }
  if (typeof types.includes === "function") {
    return (
      types.includes("Files") ||
      types.includes("application/x-moz-file") ||
      types.includes("public.file-url")
    );
  }
  return Array.from(types).some(
    (t) => t === "Files" || t === "application/x-moz-file" || t.toLowerCase().includes("file")
  );
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
 * Bulletproof Drag & Drop hook
 * - Bound once on mount with zero re-binding churn
 * - Unconditional preventDefault on dragover
 * - Synchronous FileList extraction on drop
 * - Full OS drag lifecycle and Esc cancel support
 */
export function useDragDrop(options: DragDropOptions) {
  const [isDragging, setIsDragging] = useState(false);
  const [isHoveringZone, setIsHoveringZone] = useState(false);
  
  // Stable refs for options to prevent listener recreation
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const dragDepthRef = useRef(0);
  const isDraggingRef = useRef(false);

  // Extract and filter valid files from DataTransfer
  const extractFiles = useCallback((dataTransfer: DataTransfer | null): File[] => {
    if (!dataTransfer) return [];
    
    let rawFiles: File[] = [];
    if (dataTransfer.files && dataTransfer.files.length > 0) {
      rawFiles = Array.from(dataTransfer.files);
    } else if (dataTransfer.items && dataTransfer.items.length > 0) {
      for (let i = 0; i < dataTransfer.items.length; i++) {
        const item = dataTransfer.items[i];
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) rawFiles.push(file);
        }
      }
    }

    const { multiple = true, maxFiles = 10, maxSizeBytes = 50 * 1024 * 1024 } = optionsRef.current;
    let files = rawFiles.filter((f) => f && f.size > 0 && !f.name.startsWith("."));
    
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
  }, []);

  // Window-level event listeners — BOUND ONCE ON MOUNT
  useEffect(() => {
    const handleDragEnter = (e: DragEvent) => {
      if (optionsRef.current.disabled) return;
      if (containsFiles(e.dataTransfer)) {
        e.preventDefault();
        dragDepthRef.current += 1;
        if (!isDraggingRef.current) {
          isDraggingRef.current = true;
          setIsDragging(true);
        }
      }
    };

    const handleDragOver = (e: DragEvent) => {
      if (optionsRef.current.disabled) return;
      // CRITICAL: MUST ALWAYS preventDefault on dragover for drop to fire in browser
      e.preventDefault();
      if (e.dataTransfer) {
        try {
          e.dataTransfer.dropEffect = "copy";
        } catch {}
      }
      if (containsFiles(e.dataTransfer) && !isDraggingRef.current) {
        isDraggingRef.current = true;
        setIsDragging(true);
      }
    };

    const handleDragLeave = (e: DragEvent) => {
      if (optionsRef.current.disabled) return;
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      
      // If mouse completely left window
      if (
        dragDepthRef.current === 0 ||
        e.clientX <= 0 ||
        e.clientY <= 0 ||
        e.clientX >= window.innerWidth ||
        e.clientY >= window.innerHeight
      ) {
        dragDepthRef.current = 0;
        isDraggingRef.current = false;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    };

    const handleDrop = async (e: DragEvent) => {
      if (optionsRef.current.disabled) return;
      e.preventDefault();
      e.stopPropagation();

      dragDepthRef.current = 0;
      isDraggingRef.current = false;
      setIsDragging(false);
      setIsHoveringZone(false);

      const files = extractFiles(e.dataTransfer);
      if (files.length > 0 && optionsRef.current.onDrop) {
        try {
          await optionsRef.current.onDrop(files);
        } catch (err) {
          console.error("useDragDrop onDrop handler failed:", err);
        }
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        dragDepthRef.current = 0;
        isDraggingRef.current = false;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    };

    window.addEventListener("dragenter", handleDragEnter);
    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("drop", handleDrop);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("dragenter", handleDragEnter);
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("drop", handleDrop);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [extractFiles]);

  // Synthetic event handlers for localized target zones
  const handleZoneDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsHoveringZone(true);
    if (e.dataTransfer) {
      try {
        e.dataTransfer.dropEffect = "copy";
      } catch {}
    }
  }, []);

  const handleZoneDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsHoveringZone(true);
    if (e.dataTransfer) {
      try {
        e.dataTransfer.dropEffect = "copy";
      } catch {}
    }
  }, []);

  const handleZoneDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsHoveringZone(false);
  }, []);

  const handleZoneDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragDepthRef.current = 0;
      isDraggingRef.current = false;
      setIsDragging(false);
      setIsHoveringZone(false);

      const files = extractFiles(e.dataTransfer);
      if (files.length > 0 && optionsRef.current.onDrop) {
        try {
          await optionsRef.current.onDrop(files);
        } catch (err) {
          console.error("useDragDrop zone drop failed:", err);
        }
      }
    },
    [extractFiles]
  );

  const zoneDragHandlers = {
    onDragEnter: handleZoneDragEnter,
    onDragOver: handleZoneDragOver,
    onDragLeave: handleZoneDragLeave,
    onDrop: handleZoneDrop,
  };

  return {
    isDragging,
    isHoveringZone,
    zoneDragHandlers,
    extractFiles,
  };
}
