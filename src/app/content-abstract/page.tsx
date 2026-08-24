'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';

interface PdfFile {
  name: string;
  size: number;
  sizeFormatted: string;
}

interface Parameters {
  CONFERENCE_HEADER: string;
  FOOTER_URL: string;
  LINE_SPACING_FACTOR: number;
  WORD_SPACING: number;
  TITLE_FONT_SIZE: number;
  AUTHORS_FONT_SIZE: number;
  ABSTRACT_FONT_SIZE: number;
  KEYWORDS_FONT_SIZE: number;
  HEADER_FONT_SIZE: number;
  FOOTER_URL_FONT_SIZE: number;
  FOOTER_PAGE_FONT_SIZE: number;
}

interface Toast {
  id: number;
  type: 'success' | 'error' | 'info';
  message: string;
}

const DEFAULT_PARAMS: Parameters = {
  CONFERENCE_HEADER: 'International Conference on Advances in Computer Research on Science Engineering and Technology, 2026',
  FOOTER_URL: 'www.acroset.in',
  LINE_SPACING_FACTOR: 1.45,
  WORD_SPACING: 1.5,
  TITLE_FONT_SIZE: 12,
  AUTHORS_FONT_SIZE: 9.5,
  ABSTRACT_FONT_SIZE: 10,
  KEYWORDS_FONT_SIZE: 10,
  HEADER_FONT_SIZE: 8.5,
  FOOTER_URL_FONT_SIZE: 9,
  FOOTER_PAGE_FONT_SIZE: 10,
};

// ── Minimal SVG Icons (Classic & Clean) ──
function IconFile({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function IconUpload({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function IconRefresh({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function IconSliders({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

function IconTerminal({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  );
}

function IconDownload({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function IconCheck({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconSearch({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function IconX({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export default function ContentAbstractPage() {
  const [pdfs, setPdfs] = useState<PdfFile[]>([]);
  const [params, setParams] = useState<Parameters>(DEFAULT_PARAMS);
  const [savedParams, setSavedParams] = useState<Parameters>(DEFAULT_PARAMS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState<'pdf' | 'word' | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [outputLog, setOutputLog] = useState<string>('');
  const [outputFile, setOutputFile] = useState<string | null>(null);
  const [paramsLoaded, setParamsLoaded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addToast = (type: Toast['type'], message: string) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  };

  // Fetch PDF list
  const fetchPdfs = useCallback(async () => {
    try {
      const res = await fetch('/api/pdfs');
      const data = await res.json();
      setPdfs(data.files || []);
    } catch {
      addToast('error', 'Unable to retrieve PDF documents.');
    }
  }, []);

  // Fetch parameters
  const fetchParams = useCallback(async () => {
    try {
      const res = await fetch('/api/parameters');
      const data = await res.json();
      if (data.params) {
        setParams(data.params);
        setSavedParams(data.params);
      }
      setParamsLoaded(true);
    } catch {
      setParamsLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchPdfs();
    fetchParams();
  }, [fetchPdfs, fetchParams]);

  // Save parameters
  const saveParams = async () => {
    setIsSaving(true);
    try {
      const res = await fetch('/api/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const data = await res.json();
      if (data.success) {
        setSavedParams(params);
        addToast('success', 'Layout parameters saved successfully.');
      } else {
        addToast('error', data.error || 'Failed to save configuration.');
      }
    } catch {
      addToast('error', 'Network error saving configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  // Reset to default
  const handleResetDefaults = () => {
    setParams(DEFAULT_PARAMS);
    addToast('info', 'Parameters reset to default values.');
  };

  // Upload handler
  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        addToast('success', data.message || 'Files uploaded.');
        fetchPdfs();
      } else {
        addToast('error', data.error || 'Failed to upload files.');
      }
    } catch {
      addToast('error', 'Failed to upload files.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Drag and drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  // Generate output
  const handleGenerate = async (format: 'pdf' | 'word') => {
    if (pdfs.length === 0) {
      addToast('error', 'No input PDFs available in the queue.');
      return;
    }

    setLoading(true);
    setLoadingType(format);
    setOutputLog('');
    setOutputFile(null);

    try {
      // Save params first
      await fetch('/api/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });

      const endpoint = format === 'pdf' ? '/api/generate-pdf' : '/api/generate-word';
      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();

      setOutputLog(data.output || '');

      if (data.success) {
        addToast('success', `${format.toUpperCase()} compilation complete.`);
        if (data.outputFile) {
          setOutputFile(data.outputFile);
        }
        fetchPdfs();
      } else {
        addToast('error', data.error || `Compilation failed for ${format.toUpperCase()}.`);
      }
    } catch {
      addToast('error', `An error occurred generating ${format.toUpperCase()}.`);
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  const updateParam = (key: keyof Parameters, value: string) => {
    setParams(prev => ({
      ...prev,
      [key]: typeof DEFAULT_PARAMS[key] === 'number' ? (parseFloat(value) || 0) : value,
    }));
  };

  const adjustNumeric = (key: keyof Parameters, delta: number) => {
    setParams(prev => {
      const current = Number(prev[key]) || 0;
      const next = Math.round((current + delta) * 100) / 100;
      return {
        ...prev,
        [key]: Math.max(0, next),
      };
    });
  };

  const filteredPdfs = pdfs.filter(pdf =>
    pdf.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isParamsModified = JSON.stringify(params) !== JSON.stringify(savedParams);

  return (
    <>
      {/* Toast Notifications */}
      <div className="toast-stack">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast-item ${toast.type}`}>
            {toast.type === 'success' && <IconCheck className="w-4 h-4 text-emerald-600" />}
            {toast.type === 'error' && <IconX className="w-4 h-4 text-rose-600" />}
            <span>{toast.message}</span>
          </div>
        ))}
      </div>

      {/* Top Navigation */}
      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand-section">
            <div className="brand-mark">AC</div>
            <div className="brand-meta">
              <h1 className="brand-title">ACROSET Paper Compiler</h1>
              <span className="brand-subtitle">Conference Proceedings & Abstract Engine</span>
            </div>
          </div>

          <div className="nav-actions">
            <div className="status-pill">
              <span className={`status-dot ${loading ? 'busy' : 'ready'}`} />
              <span>{loading ? `Compiling ${loadingType?.toUpperCase()}...` : 'Engine Ready'}</span>
            </div>

            {isParamsModified && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={saveParams}
                disabled={isSaving}
              >
                {isSaving ? <span className="spinner spinner-dark" /> : <IconCheck />}
                Save Changes
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="workspace-wrapper">
        <div className="page-intro">
          <div>
            <h2 className="page-headline">Content & Typesetting</h2>
            <p className="page-description">
              Manage input manuscripts, customize layout metrics, and compile final proceedings.
            </p>
          </div>

          <div className="btn-group">
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleResetDefaults}
              title="Reset parameters to original ACROSET conference defaults"
            >
              Default Config
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={saveParams}
              disabled={isSaving || !isParamsModified}
            >
              {isSaving ? <span className="spinner" /> : <IconCheck />}
              {isParamsModified ? 'Save Parameters' : 'Parameters Saved'}
            </button>
          </div>
        </div>

        <div className="dashboard-grid">
          {/* ── Left Column: Document Queue ── */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-header-title">
                <span className="panel-header-icon"><IconFile /></span>
                <span>Document Queue</span>
                <span className="file-badge">{pdfs.length} files</span>
              </div>
              <div className="btn-group">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={fetchPdfs}
                  disabled={loading}
                  title="Reload queue"
                >
                  <IconRefresh />
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  {isUploading ? <span className="spinner spinner-dark" /> : <IconUpload />}
                  Upload PDF
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  multiple
                  style={{ display: 'none' }}
                  onChange={e => handleFileUpload(e.target.files)}
                />
              </div>
            </div>

            <div className="panel-body">
              {/* Drag and Drop Box */}
              <div
                className={`dropzone-area ${dragActive ? 'drag-active' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="dropzone-icon">
                  <IconUpload />
                </div>
                <div className="dropzone-text">
                  {isUploading ? 'Uploading files...' : 'Drop manuscripts here or browse'}
                </div>
                <div className="dropzone-hint">
                  PDF documents placed here are queued for compilation
                </div>
              </div>

              {/* Search Toolbar */}
              {pdfs.length > 0 && (
                <div className="file-list-toolbar">
                  <div className="search-input-wrapper">
                    <span className="search-icon"><IconSearch /></span>
                    <input
                      type="text"
                      className="search-input"
                      placeholder="Search queue..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {/* File List */}
              {pdfs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 20px', color: 'var(--text-muted)' }}>
                  <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
                    No manuscripts in queue
                  </p>
                  <p style={{ fontSize: 12, marginTop: 4 }}>
                    Add PDFs to <code>scraper/IncompletePDF/</code> or drop them above.
                  </p>
                </div>
              ) : (
                <div className="file-list">
                  {filteredPdfs.map(pdf => {
                    const isSelected = selectedPdf === pdf.name;
                    return (
                      <div
                        key={pdf.name}
                        className={`file-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedPdf(isSelected ? null : pdf.name)}
                      >
                        <div className="file-item-left">
                          <span className="file-badge">PDF</span>
                          <span className="file-name" title={pdf.name}>
                            {pdf.name}
                          </span>
                        </div>
                        <div className="file-item-right">
                          <span className="file-size">{pdf.sizeFormatted}</span>
                          <button
                            className="file-action-btn"
                            title={isSelected ? 'Close preview' : 'Preview PDF'}
                            onClick={e => {
                              e.stopPropagation();
                              setSelectedPdf(isSelected ? null : pdf.name);
                            }}
                          >
                            {isSelected ? <IconX /> : <IconFile />}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Inline PDF Preview */}
              {selectedPdf && (
                <div className="preview-panel">
                  <div className="preview-panel-header">
                    <div className="preview-panel-title">
                      <IconFile />
                      <span>{selectedPdf}</span>
                    </div>
                    <div className="btn-group">
                      <a
                        href={`/api/pdfs?file=${encodeURIComponent(selectedPdf)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-ghost btn-sm"
                        style={{ fontSize: 11 }}
                      >
                        Open In New Tab ↗
                      </a>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setSelectedPdf(null)}
                      >
                        <IconX />
                      </button>
                    </div>
                  </div>
                  <iframe
                    className="preview-panel-frame"
                    src={`/api/pdfs?file=${encodeURIComponent(selectedPdf)}`}
                    title={`Preview: ${selectedPdf}`}
                  />
                </div>
              )}
            </div>
          </div>

          {/* ── Right Column: Layout & Parameter Studio ── */}
          <div className="panel">
            <div className="panel-header">
              <div className="panel-header-title">
                <span className="panel-header-icon"><IconSliders /></span>
                <span>Typesetting & Formatting Parameters</span>
              </div>
            </div>

            <div className="panel-body">
              {paramsLoaded && (
                <div className="form-stack">
                  {/* Section 1: Conference Metadata */}
                  <div>
                    <div className="section-tag">Conference Metadata & Headers</div>
                    <div className="field-group full-width">
                      <div className="field">
                        <label className="field-label">
                          <span>Conference Header</span>
                          <span className="field-unit">Running Head</span>
                        </label>
                        <input
                          type="text"
                          className="text-input"
                          value={params.CONFERENCE_HEADER}
                          onChange={e => updateParam('CONFERENCE_HEADER', e.target.value)}
                        />
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Footer URL</span>
                          <span className="field-unit">Domain / Link</span>
                        </label>
                        <input
                          type="text"
                          className="text-input"
                          value={params.FOOTER_URL}
                          onChange={e => updateParam('FOOTER_URL', e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Section 2: Spacing & Geometry */}
                  <div>
                    <div className="section-tag">Spacing & Line Geometry</div>
                    <div className="field-group">
                      <div className="field">
                        <label className="field-label">
                          <span>Line Spacing</span>
                          <span className="field-unit">Factor</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.05"
                            className="stepper-input"
                            value={params.LINE_SPACING_FACTOR}
                            onChange={e => updateParam('LINE_SPACING_FACTOR', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('LINE_SPACING_FACTOR', -0.05)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('LINE_SPACING_FACTOR', 0.05)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Word Spacing</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.1"
                            className="stepper-input"
                            value={params.WORD_SPACING}
                            onChange={e => updateParam('WORD_SPACING', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('WORD_SPACING', -0.1)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('WORD_SPACING', 0.1)}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Section 3: Typography Scale */}
                  <div>
                    <div className="section-tag">Typography Hierarchy</div>
                    <div className="field-group">
                      <div className="field">
                        <label className="field-label">
                          <span>Title Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.TITLE_FONT_SIZE}
                            onChange={e => updateParam('TITLE_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('TITLE_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('TITLE_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Authors Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.AUTHORS_FONT_SIZE}
                            onChange={e => updateParam('AUTHORS_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('AUTHORS_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('AUTHORS_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Abstract Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.ABSTRACT_FONT_SIZE}
                            onChange={e => updateParam('ABSTRACT_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('ABSTRACT_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('ABSTRACT_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Keywords Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.KEYWORDS_FONT_SIZE}
                            onChange={e => updateParam('KEYWORDS_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('KEYWORDS_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('KEYWORDS_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Header Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.HEADER_FONT_SIZE}
                            onChange={e => updateParam('HEADER_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('HEADER_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('HEADER_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Footer URL Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.FOOTER_URL_FONT_SIZE}
                            onChange={e => updateParam('FOOTER_URL_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('FOOTER_URL_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('FOOTER_URL_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>

                      <div className="field">
                        <label className="field-label">
                          <span>Footer Page Size</span>
                          <span className="field-unit">pt</span>
                        </label>
                        <div className="stepper-wrapper">
                          <input
                            type="number"
                            step="0.5"
                            className="stepper-input"
                            value={params.FOOTER_PAGE_FONT_SIZE}
                            onChange={e => updateParam('FOOTER_PAGE_FONT_SIZE', e.target.value)}
                          />
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('FOOTER_PAGE_FONT_SIZE', -0.5)}
                          >
                            -
                          </button>
                          <button
                            type="button"
                            className="stepper-btn"
                            onClick={() => adjustNumeric('FOOTER_PAGE_FONT_SIZE', 0.5)}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Compilation & Execution Deck ── */}
        <div className="panel action-deck">
          <div className="panel-body">
            <div className="action-bar-inner">
              <div className="action-bar-actions">
                <button
                  className="btn btn-primary btn-lg"
                  onClick={() => handleGenerate('pdf')}
                  disabled={loading || pdfs.length === 0}
                >
                  {loadingType === 'pdf' ? <span className="spinner" /> : <IconFile />}
                  {loadingType === 'pdf' ? 'Compiling Proceedings...' : 'Compile Proceedings (PDF)'}
                </button>

                <button
                  className="btn btn-secondary btn-lg"
                  onClick={() => handleGenerate('word')}
                  disabled={loading || pdfs.length === 0}
                >
                  {loadingType === 'word' ? <span className="spinner spinner-dark" /> : <IconFile />}
                  {loadingType === 'word' ? 'Generating Document...' : 'Export Word (.docx)'}
                </button>
              </div>

              <div className="btn-group">
                <button
                  className="btn btn-outline"
                  onClick={fetchPdfs}
                  disabled={loading}
                >
                  <IconRefresh />
                  Sync Queue
                </button>
              </div>
            </div>

            {/* Output Download Banner */}
            {outputFile && (
              <div className="download-card">
                <div className="download-card-meta">
                  <div className="download-card-icon">
                    <IconCheck />
                  </div>
                  <div>
                    <div className="download-card-title">Compilation Successful</div>
                    <div className="download-card-desc">
                      Generated <strong>{outputFile}</strong> with all current layout specifications.
                    </div>
                  </div>
                </div>
                <a
                  href={`/api/download?file=${encodeURIComponent(outputFile)}`}
                  download
                  className="btn btn-primary btn-sm"
                >
                  <IconDownload />
                  Download File
                </a>
              </div>
            )}

            {/* Terminal Output Log */}
            {outputLog && (
              <div className="terminal-panel">
                <div className="terminal-header">
                  <div className="terminal-header-title">
                    <span className="terminal-dot" />
                    <span>compiler-output.log</span>
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ color: 'var(--text-terminal-muted)', height: 24, fontSize: 11 }}
                    onClick={() => {
                      navigator.clipboard.writeText(outputLog);
                      addToast('info', 'Logs copied to clipboard.');
                    }}
                  >
                    Copy Output
                  </button>
                </div>
                <pre className="terminal-body">{outputLog}</pre>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
