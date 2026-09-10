"use client";

import React, { useState, useRef } from "react";
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

export function DocumentVault() {
  const { documents, loading, uploading, upload, remove } = useDocuments();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleFilesUpload = async (files: FileList | File[]) => {
    const fileList = Array.from(files);
    if (!fileList.length) return;
    
    let successCount = 0;
    for (const file of fileList) {
      try {
        await upload(file);
        successCount++;
      } catch (err) {
        toast.error(`Failed to ingest "${file.name}": ${(err as Error).message}`);
      }
    }
    if (successCount > 0) {
      toast.success(`Successfully ingested and indexed ${successCount} document${successCount > 1 ? "s" : ""}.`);
    }
  };

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
    <div className="flex flex-col h-full bg-slate-50 p-5 overflow-y-auto space-y-4">
      {/* Upload Header & Drag-Drop Well */}
      <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs">
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
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs font-semibold shadow-xs transition-all disabled:opacity-50 cursor-pointer"
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
              accept=".pdf,.docx,.doc,.txt,.md,.json,.jsonl,.csv"
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

        {/* Drag and drop target area */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(true);
          }}
          onDragEnter={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(false);
          }}
          onDrop={async (e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(false);
            if (e.dataTransfer.files?.length) {
              await handleFilesUpload(e.dataTransfer.files);
            }
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`mt-4 border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
            dragOver
              ? "border-blue-500 bg-blue-50/80 scale-[1.01] shadow-sm"
              : "border-slate-200 hover:border-blue-400 hover:bg-blue-50/30 bg-slate-50/50"
          }`}
        >
          <Upload size={24} className={`mx-auto mb-2 transition-colors ${dragOver ? "text-blue-600 animate-bounce" : "text-slate-400"}`} />
          <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
            {dragOver ? "Drop files here to start indexing..." : "Drag & drop multiple files here, or click to browse"}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Supports PDF, DOCX, Markdown (.md), TXT, CSV, JSON (max 25MB per file)
          </div>
        </div>

        {/* Precomputed Chunk Variants Ribbon */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-100">
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Variant A (Dense)
            </span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">500 chars / 50 overlap</div>
            <span className="text-[10px] text-slate-500">Fast precise retrieval for factual claims</span>
          </div>
          <div className="p-2.5 rounded-lg bg-blue-50/70 border border-blue-200/80">
            <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider">
              Variant B (Optimal)
            </span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">700 chars / 100 overlap</div>
            <span className="text-[10px] text-slate-500">AES champion balance between context &amp; focus</span>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Variant C (Broad)
            </span>
            <div className="text-xs font-semibold text-slate-800 mt-0.5">1500 chars / 300 overlap</div>
            <span className="text-[10px] text-slate-500">Macro section synthesis for complex reasoning</span>
          </div>
        </div>
      </div>

      {/* Document List Card */}
      <div className="bg-white border border-slate-200/90 rounded-xl overflow-hidden shadow-xs">
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
