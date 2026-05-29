const handleUpload = async () => {
  if (!files?.length) {
    setError('Please select one or more CSV files');
    return;
  }

  const invalid = files.find(
    (f) => !f?.name?.toLowerCase()?.endsWith('.csv')
  );

  if (invalid) {
    setError('Only CSV files are supported');
    return;
  }

  if (files.length > 30) {
    setError('You can upload a maximum of 30 files at a time');
    return;
  }

  setError('');
  setMessage('');
  setLoading(true);

  setResults(
    files.map((f, idx) => ({
      id: `${f.name}-${f.size}-${f.lastModified}-${idx}`,
      file: f,
      status: 'uploading',
      progress: 100,
      response: null,
      error: null,
    }))
  );

  try {
    setMessage(
      'Uploading files… per-file mapping/normalization/missing summaries will appear after upload.'
    );

    const responses = await uploadCSVFiles(files);

    setResults((prev) =>
      prev.map((r, idx) => ({
        ...r,
        status: 'completed',
        progress: 100,
        response: Array.isArray(responses)
          ? responses[idx]
          : responses,
      }))
    );

    triggerAppRefresh();
    setFiles([]);
  } catch (err) {
    setError(formatError(err, 'Upload failed'));

    setResults((prev) =>
      prev.map((r) => ({
        ...r,
        status: 'failed',
        error: formatError(err, 'Upload failed'),
      }))
    );
  } finally {
    setLoading(false);
  }
};