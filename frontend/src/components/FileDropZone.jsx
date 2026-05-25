import { useRef, useState } from 'react';

export default function FileDropZone({
  accept = '.csv',
  disabled = false,
  file,
  onFileSelect,
  hint = 'Drag and drop a CSV file here, or click to browse',
}) {
  const inputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const pickFile = (selected) => {
    if (!selected || disabled) return;
    onFileSelect(selected);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    pickFile(dropped);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const openPicker = () => {
    if (!disabled) inputRef.current?.click();
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="dropzone-wrap">
      <div
        className={`dropzone ${dragOver ? 'dropzone-active' : ''} ${file ? 'dropzone-has-file' : ''}`}
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
          className="dropzone-input"
          disabled={disabled}
          onChange={(e) => pickFile(e.target.files?.[0] || null)}
          onClick={(e) => e.stopPropagation()}
        />
        {!file ? (
          <>
            <span className="dropzone-icon" aria-hidden="true">
              ↑
            </span>
            <p className="dropzone-hint">{hint}</p>
            <span className="dropzone-formats">Accepted: {accept}</span>
          </>
        ) : (
          <div className="dropzone-preview" onClick={(e) => e.stopPropagation()}>
            <div className="dropzone-preview-icon" aria-hidden="true">
              CSV
            </div>
            <div className="dropzone-preview-meta">
              <strong>{file.name}</strong>
              <span>{formatSize(file.size)}</span>
            </div>
            <button
              type="button"
              className="dropzone-remove"
              disabled={disabled}
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
                if (inputRef.current) inputRef.current.value = '';
              }}
            >
              Remove
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
