import { useMemo, useRef, useState } from 'react';
import { SUPPORTED_FORMATS_MESSAGE, UPLOAD_ACCEPT } from '../constants/uploadFormats';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function toArray(fileList) {
  if (!fileList) return [];
  return Array.from(fileList);
}

export default function MultiFileDropZone({
  accept = UPLOAD_ACCEPT,
  disabled = false,
  files = [],
  onFilesChange,
  maxFiles = 30,
  hint = 'Drag and drop files here, or click to browse',
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const totalSize = useMemo(
    () => (files || []).reduce((sum, f) => sum + (f?.size || 0), 0),
    [files]
  );

  const pickFiles = (selectedList) => {
    if (disabled) return;
    const selected = toArray(selectedList).filter(Boolean);
    if (!selected.length) return;

    const next = [...(files || [])];
    for (const f of selected) {
      if (next.length >= maxFiles) break;
      // de-dupe by name + size + lastModified
      const key = `${f.name}-${f.size}-${f.lastModified}`;
      const exists = next.some(
        (x) => `${x.name}-${x.size}-${x.lastModified}` === key
      );
      if (!exists) next.push(f);
    }
    onFilesChange(next);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    pickFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const removeAt = (idx) => {
    const next = [...(files || [])];
    next.splice(idx, 1);
    onFilesChange(next);
    if (inputRef.current && next.length === 0) inputRef.current.value = '';
  };

  const clearAll = () => {
    onFilesChange([]);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="dropzone-wrap">
      <div
        className={`dropzone ${dragOver ? 'dropzone-active' : ''} ${
          files?.length ? 'dropzone-has-file' : ''
        }`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openPicker();
          }
        }}
        onClick={openPicker}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        aria-disabled={disabled}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple
          className="dropzone-input"
          disabled={disabled}
          onChange={(e) => pickFiles(e.target.files)}
          onClick={(e) => e.stopPropagation()}
        />

        {!files?.length ? (
          <>
            <span className="dropzone-icon" aria-hidden="true">
              ↑
            </span>
            <p className="dropzone-hint">{hint}</p>
            <span className="dropzone-formats">
              {SUPPORTED_FORMATS_MESSAGE} • Max files: {maxFiles}
            </span>
          </>
        ) : (
          <div className="dropzone-preview" onClick={(e) => e.stopPropagation()}>
            <div className="dropzone-preview-meta" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <strong>
                  {files.length} file(s) selected
                </strong>
                <span>{formatSize(totalSize)}</span>
              </div>
              <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                {files.map((f, idx) => (
                  <div
                    key={`${f.name}-${f.size}-${f.lastModified}-${idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '6px 8px',
                      border: '1px solid #e6e9ef',
                      borderRadius: 8,
                      background: '#fff',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {f.name}
                      </div>
                      <div style={{ fontSize: 12, opacity: 0.75 }}>{formatSize(f.size)}</div>
                    </div>
                    <button
                      type="button"
                      className="dropzone-remove"
                      disabled={disabled}
                      onClick={(e) => {
                        e.stopPropagation();
                        removeAt(idx);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  className="dropzone-remove"
                  disabled={disabled}
                  onClick={(e) => {
                    e.stopPropagation();
                    clearAll();
                  }}
                >
                  Clear all
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

