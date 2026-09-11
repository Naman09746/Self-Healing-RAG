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
 * Production-grade Drag & Drop hook
 * Captures window & zone drops flawlessly, handles file extraction,
 * prevents double-triggers, supports Esc key, and provides smooth UI state.
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
  const lastDropTimestamp = useRef(0);
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

  const processAndDispatchDrop = useCallback(
    async (dataTransfer: DataTransfer | null) => {
      // Debounce frame to prevent double dispatch between window & element
      const now = Date.now();
      if (now - lastDropTimestamp.current < 200) return;
      lastDropTimestamp.current = now;

      dragCounter.current = 0;
      setIsDragging(false);
      setIsHoveringZone(false);

      if (!dataTransfer) return;

      let rawFiles: File[] = [];
      if (dataTransfer.files && dataTransfer.files.length > 0) {
        rawFiles = Array.from(dataTransfer.files);
      } else if (dataTransfer.items) {
        rawFiles = Array.from(dataTransfer.items)
          .filter((it) => it.kind === "file")
          .map((it) => it.getAsFile())
          .filter(Boolean) as File[];
      }

      const validFiles = filterFiles(rawFiles);
      if (validFiles.length > 0) {
        try {
          await onDropRef.current(validFiles);
        } catch (err) {
          console.error("useDragDrop onDrop failed:", err);
        }
      }
    },
    [filterFiles]
  );

  // Global window listeners for drag & drop
  useEffect(() => {
    if (disabled) return;

    const handleWindowDragEnter = (e: DragEvent) => {
      if (containsFiles(e.dataTransfer)) {
        e.preventDefault();
        dragCounter.current += 1;
        setIsDragging(true);
      }
    };

    const handleWindowDragOver = (e: DragEvent) => {
      if (containsFiles(e.dataTransfer)) {
        e.preventDefault();
        if (e.dataTransfer) {
          e.dataTransfer.dropEffect = "copy";
        }
        if (!isDragging) {
          setIsDragging(true);
        }
      }
    };

    const handleWindowDragLeave = (e: DragEvent) => {
      dragCounter.current -= 1;
      // If mouse leaves the window entirely or counter resets
      if (
        dragCounter.current <= 0 ||
        e.clientX <= 0 ||
        e.clientY <= 0 ||
        e.clientX >= window.innerWidth ||
        e.clientY >= window.innerHeight
      ) {
        dragCounter.current = 0;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    };

    const handleWindowDrop = async (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      await processAndDispatchDrop(e.dataTransfer);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        dragCounter.current = 0;
        setIsDragging(false);
        setIsHoveringZone(false);
      }
    };

    window.addEventListener("dragenter", handleWindowDragEnter);
    window.addEventListener("dragover", handleWindowDragOver);
    window.addEventListener("dragleave", handleWindowDragLeave);
    window.addEventListener("drop", handleWindowDrop);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("dragenter", handleWindowDragEnter);
      window.removeEventListener("dragover", handleWindowDragOver);
      window.removeEventListener("dragleave", handleWindowDragLeave);
      window.removeEventListener("drop", handleWindowDrop);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [disabled, isDragging, processAndDispatchDrop]);

  // React synthetic event handlers for specific zones
  const handleZoneDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer && containsFiles(e.dataTransfer)) {
      e.dataTransfer.dropEffect = "copy";
      setIsHoveringZone(true);
    }
  }, []);

  const handleZoneDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer && containsFiles(e.dataTransfer)) {
      e.dataTransfer.dropEffect = "copy";
      setIsHoveringZone(true);
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
      await processAndDispatchDrop(e.dataTransfer);
    },
    [processAndDispatchDrop]
  );

  const zoneDragHandlers = {
    onDragEnter: handleZoneDragEnter,
    onDragOver: handleZoneDragOver,
    onDragLeave: handleZoneDragLeave,
    onDrop: handleZoneDrop,
  };

  const containerDragHandlers = {
    onDragEnter: handleZoneDragEnter,
    onDragOver: handleZoneDragOver,
    onDragLeave: handleZoneDragLeave,
    onDrop: handleZoneDrop,
  };

  return {
    isDragging,
    isHoveringZone,
    dragHandlers: containerDragHandlers,
    zoneDragHandlers,
    filterFiles,
  };
}
