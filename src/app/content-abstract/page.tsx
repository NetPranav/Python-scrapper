'use client';

import { useState, useEffect, useCallback } from 'react';

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

export default function ContentAbstractPage() {
  const [pdfs, setPdfs] = useState<PdfFile[]>([]);
  const [params, setParams] = useState<Parameters>(DEFAULT_PARAMS);
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState<'pdf' | 'word' | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [outputLog, setOutputLog] = useState<string>('');
  const [outputFile, setOutputFile] = useState<string | null>(null);
  const [paramsLoaded, setParamsLoaded] = useState(false);

  // Fetch PDF list
  const fetchPdfs = useCallback(async () => {
    try {
      const res = await fetch('/api/pdfs');
      const data = await res.json();
      setPdfs(data.files || []);
    } catch {
      addToast('error', 'Failed to load PDF list');
    }
  }, []);

  // Fetch parameters
  const fetchParams = useCallback(async () => {
    try {
      const res = await fetch('/api/parameters');
      const data = await res.json();
      if (data.params) {
        setParams(data.params);
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

  // Toast management
  const addToast = (type: Toast['type'], message: string) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  };

  // Save parameters
  const saveParams = async () => {
    try {
      const res = await fetch('/api/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const data = await res.json();
      if (data.success) {
        addToast('success', 'Parameters saved successfully');
      } else {
        addToast('error', data.error || 'Failed to save parameters');
      }
    } catch {
      addToast('error', 'Failed to save parameters');
    }
  };

  // Generate output
  const handleGenerate = async (format: 'pdf' | 'word') => {
    if (pdfs.length === 0) {
      addToast('error', 'No PDFs found in IncompletePDF folder');
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
        addToast('success', `${format.toUpperCase()} generated successfully!`);
        if (data.outputFile) {
          setOutputFile(data.outputFile);
        }
        // Refresh PDF list (some may have moved)
        fetchPdfs();
      } else {
        addToast('error', data.error || `Failed to generate ${format.toUpperCase()}`);
      }
    } catch {
      addToast('error', `Failed to generate ${format.toUpperCase()}`);
    } finally {
      setLoading(false);
      setLoadingType(null);
    }
  };

  const updateParam = (key: keyof Parameters, value: string) => {
    setParams(prev => ({
      ...prev,
      [key]: typeof DEFAULT_PARAMS[key] === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  return (
    <>
      {/* Toast Container */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            {toast.type === 'success' && '✅'}
            {toast.type === 'error' && '❌'}
            {toast.type === 'info' && 'ℹ️'}
            {toast.message}
          </div>
        ))}
      </div>

      <div className="page-header">
        <h1 className="page-title">Content & Abstract</h1>
        <p className="page-subtitle">
          Configure parameters, preview PDFs, and generate compiled output
        </p>
      </div>

      {/* ── Parameter Controls ── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title">
          <span className="card-title-icon">⚙️</span>
          Layout Parameters
          <div style={{ flex: 1 }} />
          <button className="btn btn-outline" onClick={saveParams} style={{ padding: '8px 16px', fontSize: 12 }}>
            💾 Save Parameters
          </button>
        </div>

        {paramsLoaded && (
          <>
            {/* Text Content */}
            <div className="param-section">
              <div className="param-section-title">📝 Text Content</div>
              <div className="param-grid">
                <div className="param-item param-input-wide">
                  <label className="param-label">Conference Header</label>
                  <input
                    className="param-input"
                    value={params.CONFERENCE_HEADER}
                    onChange={e => updateParam('CONFERENCE_HEADER', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Footer URL</label>
                  <input
                    className="param-input"
                    value={params.FOOTER_URL}
                    onChange={e => updateParam('FOOTER_URL', e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Spacing */}
            <div className="param-section">
              <div className="param-section-title">📐 Spacing</div>
              <div className="param-grid">
                <div className="param-item">
                  <label className="param-label">Line Spacing Factor</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.05"
                    value={params.LINE_SPACING_FACTOR}
                    onChange={e => updateParam('LINE_SPACING_FACTOR', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Word Spacing (pt)</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.1"
                    value={params.WORD_SPACING}
                    onChange={e => updateParam('WORD_SPACING', e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Font Sizes */}
            <div className="param-section">
              <div className="param-section-title">🔤 Font Sizes</div>
              <div className="param-grid">
                <div className="param-item">
                  <label className="param-label">Title Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.TITLE_FONT_SIZE}
                    onChange={e => updateParam('TITLE_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Authors Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.AUTHORS_FONT_SIZE}
                    onChange={e => updateParam('AUTHORS_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Abstract Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.ABSTRACT_FONT_SIZE}
                    onChange={e => updateParam('ABSTRACT_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Keywords Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.KEYWORDS_FONT_SIZE}
                    onChange={e => updateParam('KEYWORDS_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Header Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.HEADER_FONT_SIZE}
                    onChange={e => updateParam('HEADER_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Footer URL Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.FOOTER_URL_FONT_SIZE}
                    onChange={e => updateParam('FOOTER_URL_FONT_SIZE', e.target.value)}
                  />
                </div>
                <div className="param-item">
                  <label className="param-label">Footer Page Font Size</label>
                  <input
                    className="param-input"
                    type="number"
                    step="0.5"
                    value={params.FOOTER_PAGE_FONT_SIZE}
                    onChange={e => updateParam('FOOTER_PAGE_FONT_SIZE', e.target.value)}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── PDF List ── */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title">
          <span className="card-title-icon">📁</span>
          PDFs in IncompletePDF
          <div style={{ flex: 1 }} />
          <span className="status-badge status-badge-ready">
            {pdfs.length} file{pdfs.length !== 1 ? 's' : ''}
          </span>
        </div>

        {pdfs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            <p style={{ fontSize: 32, marginBottom: 12 }}>📭</p>
            <p>No PDFs found. Add PDF files to the <code>scraper/IncompletePDF/</code> folder.</p>
          </div>
        ) : (
          <div className="pdf-grid">
            {pdfs.map(pdf => (
              <div
                key={pdf.name}
                className={`pdf-card ${selectedPdf === pdf.name ? 'selected' : ''}`}
                onClick={() => setSelectedPdf(selectedPdf === pdf.name ? null : pdf.name)}
              >
                <div className="pdf-icon">PDF</div>
                <div className="pdf-info">
                  <div className="pdf-name">{pdf.name}</div>
                  <div className="pdf-size">{pdf.sizeFormatted || formatSize(pdf.size)}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* PDF Preview */}
        {selectedPdf && (
          <div className="pdf-preview-container">
            <div className="pdf-preview-header">
              <span className="pdf-preview-title">📄 {selectedPdf}</span>
              <button className="pdf-preview-close" onClick={() => setSelectedPdf(null)}>
                ✕ Close
              </button>
            </div>
            <iframe
              className="pdf-preview-iframe"
              src={`/api/pdfs?file=${encodeURIComponent(selectedPdf)}`}
              title={`Preview: ${selectedPdf}`}
            />
          </div>
        )}
      </div>

      {/* ── Action Buttons ── */}
      <div className="card">
        <div className="card-title">
          <span className="card-title-icon">🚀</span>
          Generate Output
        </div>

        <div className="action-bar">
          <button
            className="btn btn-primary"
            onClick={() => handleGenerate('pdf')}
            disabled={loading || pdfs.length === 0}
          >
            {loadingType === 'pdf' ? <span className="spinner" /> : '📄'}
            {loadingType === 'pdf' ? 'Generating PDF...' : 'Generate PDF'}
          </button>

          <button
            className="btn btn-green"
            onClick={() => handleGenerate('word')}
            disabled={loading || pdfs.length === 0}
          >
            {loadingType === 'word' ? <span className="spinner" /> : '📝'}
            {loadingType === 'word' ? 'Generating Word...' : 'Generate Word'}
          </button>

          <button
            className="btn btn-outline"
            onClick={fetchPdfs}
            disabled={loading}
          >
            🔄 Refresh
          </button>
        </div>

        {/* Output Log */}
        {outputLog && (
          <div className="output-panel">
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
              📋 Output Log
            </div>
            <pre className="output-log">{outputLog}</pre>
          </div>
        )}

        {/* Download Link */}
        {outputFile && (
          <a
            className="download-link"
            href={`/api/download?file=${encodeURIComponent(outputFile)}`}
            download
          >
            ⬇️ Download {outputFile}
          </a>
        )}
      </div>
    </>
  );
}
