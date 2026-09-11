"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  Upload,
  FileText,
  Trash2,
  Loader2,
  Search,
  CheckCircle2,
  HardDrive,
  Filter,
} from "lucide-react";
import { useDocuments } from "@/lib/hooks";
import { useToast } from "@/components/Toast";
import { useDragDrop } from "@/lib/useDragDrop";

export function DocumentVault() {
  const { documents, loading, uploading, upload, remove } = useDocuments();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleFilesUpload = useCallback(
    async (files: FileList | File[]) => {
      const fileList = Array.isArray(files) ? files : Array.from(files as FileList);
      if (!fileList.length) return;

      let successCount = 0;
      for (const file of fileList) {
        try {
          await upload(file);
          successCount++;
        } catch (err) {
          const raw = (err as Error).message || "Upload failed";
          const clean = raw.length > 120 ? `${raw.slice(0, 117)}...` : raw;
          toast.error(`Failed to ingest "${file.name}": ${clean}`);
        }
      }
      if (successCount > 0) {
        toast.success(
          `Successfully indexed ${successCount} document${successCount > 1 ? "s" : ""} into vector & sparse storage.`
        );
      }
    },
    [upload, toast]
  );

  const { isHoveringZone: dragOver, zoneDragHandlers } = useDragDrop({
    onDrop: handleFilesUpload,
    multiple: true,
    maxFiles: 10,
  });

  const handleRemove = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}" from the vector store?`)) return;
    try {
      await remove(id);
      toast.success(`Removed "${name}" from collection.`);
    } catch (err) {
      toast.error(`Failed to delete document: ${(err as Error).message}`);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-slate-50 via-white to-blue-50/20 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 p-5 overflow-y-auto space-y-4">
      {/* Upload Header & Drag-Drop Well — light glassy */}
      <div className="bg-white/80 dark:bg-slate-900/70 backdrop-blur-xl border border-white/60 dark:border-slate-800/60 rounded-2xl p-5 shadow-[0_8px_32px_rgba(15,23,42,0.06)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
                <HardDrive size={15} />
              </div>
              <h2 className="text-sm font-bold text-slate-900">
                Indexed Document Corpus &amp; Chunk Variants
              </h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Upload PDF, DOCX, Markdown, or TXT documents. Documents are chunked, embedded, and stored across pgvector/Chroma and sparse search indexes.
            </p>
          </div>

          <div>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 active:from-blue-800 active:to-indigo-800 text-white text-xs font-semibold shadow-[0_4px_16px_rgba(37,99,235,0.25)] hover:shadow-[0_6px_20px_rgba(37,99,235,0.3)] transition-all disabled:opacity-50 cursor-pointer"
            >
              {uploading ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  <span>Ingesting &amp; Indexing…</span>
                </>
              ) : (
                <>
                  <Upload size={13} />
                  <span>Upload Documents</span>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.odt,.rtf,.pptx,.ppt,.xlsx,.xls,.ods,.csv,.tsv,.html,.htm,.xml,.json,.jsonl,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.gif,.epub"
              className="hidden"
              onChange={async (e) => {
                if (e.target.files?.length) {
                  await handleFilesUpload(e.target.files);
                  e.target.value = "";
                }
              }}
            />
          </div>
        </div>

        {/* Drag and drop target area — light glassy, never dark — unified hook */}
        <div
          {...zoneDragHandlers}
          onClick={() => fileInputRef.current?.click()}
          role="region"
          aria-label="File drop zone"
          aria-dropeffect="copy"
          className={`mt-4 relative overflow-hidden border-2 border-dashed rounded-2xl p-7 text-center cursor-pointer transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            dragOver
              ? "border-blue-400/60 bg-gradient-to-br from-white/90 via-blue-50/50 to-indigo-50/20 dark:from-slate-800/60 dark:via-blue-900/15 dark:to-indigo-900/10 backdrop-blur-2xl shadow-[0_16px_48px_rgba(37,99,235,0.18)] ring-1 ring-blue-200/50 dark:ring-blue-500/25 scale-[1.02]"
              : "border-slate-200/60 dark:border-slate-700/50 bg-white/60 dark:bg-slate-800/30 backdrop-blur-md hover:border-slate-300/80 dark:hover:border-slate-600/50 hover:bg-white/80 dark:hover:bg-slate-800/50 hover:shadow-[0_4px_20px_rgba(15,23,42,0.06)] dark:hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]"
          }`}
        >
          {/* Subtle glass highlight */}
          <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/40 via-transparent to-transparent dark:from-white/[0.03] opacity-60" />
          <div className="relative">
            <div className={`mx-auto mb-3 w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 ${dragOver ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-[0_6px_20px_rgba(37,99,235,0.3)] scale-110" : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200/50 dark:border-slate-700/50"}`}>
              <Upload size={20} className={`${dragOver ? "animate-bounce" : ""} transition-colors`} />
            </div>
            <div className={`text-sm font-semibold transition-colors ${dragOver ? "text-blue-700 dark:text-blue-300" : "text-slate-800 dark:text-slate-200"}`}>
              {dragOver ? "Drop files here to start indexing..." : "Drag & drop files here, or click to browse"}
            </div>
            <div className={`text-[11px] mt-1.5 max-w-md mx-auto leading-relaxed transition-colors ${dragOver ? "text-blue-600/80 dark:text-blue-400/80" : "text-slate-500 dark:text-slate-400"}`}>
              Supports <span className="font-medium">PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, HTML, JSON</span> + images <span className="font-medium">(PNG/JPG/WEBP/TIFF via OCR)</span> — up to <span className="font-semibold">50 MB</span> per file, <span className="font-semibold">10</span> files batch
            </div>
            {dragOver && (
              <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-600 text-white text-[10px] font-semibold shadow-sm animate-pulse">
                <div className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                Release to upload
              </div>
            )}
          </div>
        </div>

        {/* Precomputed Chunk Variants Ribbon — production 1000/200 default */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5 pt-5 border-t border-slate-200/40 dark:border-slate-800/40">
          <div className="p-3 rounded-xl bg-white/60 dark:bg-slate-800/30 backdrop-blur-md border border-slate-200/50 dark:border-slate-700/30 hover:bg-white/80 dark:hover:bg-slate-800/50 transition-colors">
            <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Variant A (Dense)
            </span>
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-0.5">500 chars / 50 overlap</div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400">Precise factual claims, low latency</span>
          </div>
          <div className="p-3 rounded-xl bg-gradient-to-br from-blue-50/80 via-indigo-50/50 to-white/60 dark:from-blue-950/30 dark:via-indigo-950/20 dark:to-slate-800/30 backdrop-blur-md border border-blue-200/60 dark:border-blue-800/40 shadow-[0_4px_16px_rgba(37,99,235,0.08)] dark:shadow-none">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold text-blue-700 dark:text-blue-300 uppercase tracking-wider">
                Variant B (Active)
              </span>
              <span className="text-[8px] font-bold px-1 py-0 rounded bg-blue-600 text-white">DEFAULT</span>
            </div>
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-0.5">1000 chars / 200 overlap</div>
            <span className="text-[10px] text-slate-600 dark:text-slate-400">Production default — balanced context &amp; focus</span>
          </div>
          <div className="p-3 rounded-xl bg-white/60 dark:bg-slate-800/30 backdrop-blur-md border border-slate-200/50 dark:border-slate-700/30 hover:bg-white/80 dark:hover:bg-slate-800/50 transition-colors">
            <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Variant C (Broad)
            </span>
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-0.5">1500 chars / 300 overlap</div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400">Long-form synthesis, complex reasoning</span>
          </div>
        </div>
      </div>

      {/* Document List Card — light glassy */}
      <div className="bg-white/80 dark:bg-slate-900/60 backdrop-blur-xl border border-white/60 dark:border-slate-800/60 rounded-2xl overflow-hidden shadow-[0_8px_32px_rgba(15,23,42,0.06)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.25)]">
        <div className="px-5 py-3.5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span className="text-xs font-bold text-slate-900">
            All Documents ({filteredDocs.length}{searchQuery && ` of ${documents.length}`})
          </span>

          <div className="relative w-full sm:w-64">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents by name…"
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {loading && documents.length === 0 && (
            <div className="py-12 flex items-center justify-center gap-2 text-xs text-slate-500">
              <Loader2 size={14} className="animate-spin text-blue-600" />
              <span>Fetching index status…</span>
            </div>
          )}

          {!loading && documents.length === 0 && (
            <div className="py-12 text-center text-xs text-slate-500">
              No documents indexed in this collection. Click &ldquo;Upload Documents&rdquo; to begin.
            </div>
          )}

          {filteredDocs.map((doc) => (
            <div
              key={doc.id}
              className="p-3.5 flex items-center justify-between hover:bg-slate-50/80 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200/60 flex items-center justify-center shrink-0">
                  <FileText size={14} className="text-blue-600" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-900 truncate">
                      {doc.filename}
                    </span>
                    <span
                      className={`text-[9px] font-medium px-1.5 py-0.5 rounded border ${
                        doc.status === "indexed"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : doc.status === "processing"
                          ? "bg-amber-50 text-amber-700 border-amber-200"
                          : "bg-rose-50 text-rose-700 border-rose-200"
                      }`}
                    >
                      {doc.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-0.5">
                    <span>{doc.chunks} chunks</span>
                    <span>•</span>
                    <span>Indexed {doc.created_at?.split("T")[0] || "recently"}</span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleRemove(doc.id, doc.filename)}
                className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                title="Delete document"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
