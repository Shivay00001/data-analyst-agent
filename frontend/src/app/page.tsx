'use client';

import { useState, useEffect } from 'react';

export default function Home() {
  const [provider, setProvider] = useState('gpt-4o');
  const [keys, setKeys] = useState({ openai: '', anthropic: '', gemini: '', glm: '' });
  const [file, setFile] = useState<File | null>(null);
  const [datasetPath, setDatasetPath] = useState('');
  const [prompt, setPrompt] = useState('Group sales by month and plot a bar chart of total revenue.');
  
  const [status, setStatus] = useState<'idle' | 'uploading' | 'pending' | 'running' | 'completed' | 'failed'>('idle');
  const [uploadMessage, setUploadMessage] = useState('');
  
  const [generatedCode, setGeneratedCode] = useState('');
  const [executionOutput, setExecutionOutput] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const [taskId, setTaskId] = useState('');

  useEffect(() => {
    setKeys({
      openai: localStorage.getItem('da_openai_key') || '',
      anthropic: localStorage.getItem('da_anthropic_key') || '',
      gemini: localStorage.getItem('da_gemini_key') || '',
      glm: localStorage.getItem('da_glm_key') || ''
    });

    let interval: NodeJS.Timeout;
    if (taskId && (status === 'pending' || status === 'running')) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`http://localhost:8002/api/tasks/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            setStatus(data.status);
            setGeneratedCode(data.generated_code || 'Awaiting instructions...');
            setExecutionOutput(data.execution_output || 'Processing request...');
            
            if (data.images && data.images.length > 0 && data.images[0] !== "") {
              setImages(data.images);
            }

            if (data.status === 'completed' || data.status === 'failed') {
              clearInterval(interval);
            }
          }
        } catch (e) {
          console.error("Polling error", e);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, status]);

  const handleKeyChange = (p: string, val: string) => {
    setKeys(prev => ({...prev, [p]: val}));
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      setStatus('uploading');
      setUploadMessage('Uploading...');
      try {
        const res = await fetch('http://localhost:8002/api/datasets/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        setDatasetPath(data.filepath);
        setUploadMessage(`Uploaded: ${data.filename}`);
        setStatus('idle');
      } catch (err) {
        setUploadMessage('Upload failed.');
        setStatus('idle');
      }
    }
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!datasetPath) {
      alert("Please upload a dataset first.");
      return;
    }
    
    setStatus('pending');
    setGeneratedCode('Submitting task to background queue...');
    setExecutionOutput('');
    setImages([]);
    
    try {
      localStorage.setItem('da_openai_key', keys.openai);
      localStorage.setItem('da_anthropic_key', keys.anthropic);
      localStorage.setItem('da_gemini_key', keys.gemini);
      localStorage.setItem('da_glm_key', keys.glm);

      const res = await fetch('http://localhost:8002/api/execute', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-OpenAI-Key': keys.openai,
          'X-Anthropic-Key': keys.anthropic,
          'X-Gemini-Key': keys.gemini,
          'X-GLM-Key': keys.glm
        },
        body: JSON.stringify({
          prompt,
          provider,
          dataset_filepath: datasetPath
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setTaskId(data.task_id);
      } else {
        setStatus('failed');
        setGeneratedCode('Failed to submit task.');
      }
    } catch (err) {
      setStatus('failed');
      setGeneratedCode('Error communicating with backend.');
    }
  };

  return (
    <main className="dashboard-container">
      <div className="header">
        <h1>Data Analyst Agent</h1>
        <p>Business Intelligence & Descriptive Analytics (Async Production)</p>
      </div>

      <div className="grid-layout">
        <div className="panel" style={{ alignSelf: 'start' }}>
          <h2 className="panel-title">Query Configuration</h2>
          
          <form onSubmit={handleExecute}>
            <div className="form-group">
              <label>OpenAI (GPT-4o)</label>
              <input type="password" value={keys.openai} onChange={(e) => handleKeyChange('openai', e.target.value)} disabled={status === 'pending' || status === 'running'} />
            </div>
            <div className="form-group">
              <label>Anthropic (Claude 3.5)</label>
              <input type="password" value={keys.anthropic} onChange={(e) => handleKeyChange('anthropic', e.target.value)} disabled={status === 'pending' || status === 'running'} />
            </div>
            <div className="form-group">
              <label>Google AI (Gemini 1.5)</label>
              <input type="password" value={keys.gemini} onChange={(e) => handleKeyChange('gemini', e.target.value)} disabled={status === 'pending' || status === 'running'} />
            </div>
            <div className="form-group">
              <label>ZhipuAI (GLM-4)</label>
              <input type="password" value={keys.glm} onChange={(e) => handleKeyChange('glm', e.target.value)} disabled={status === 'pending' || status === 'running'} />
            </div>

            <div className="form-group">
              <label>LLM Provider (Privacy Toggle)</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={status === 'pending' || status === 'running'}>
                <option value="gpt-4o">OpenAI (gpt-4o)</option>
                <option value="claude-3-5-sonnet-20240620">Anthropic (claude-3-5-sonnet)</option>
                <option value="gemini/gemini-1.5-pro">Google AI (gemini-1.5-pro)</option>
                <option value="zhipu/glm-4">ZhipuAI (glm-4)</option>
                <option value="ollama/llama3">Local Ollama (Llama 3)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Dataset (CSV)</label>
              <input type="file" accept=".csv" onChange={handleUpload} disabled={status === 'pending' || status === 'running'} />
              {uploadMessage && <div style={{ marginTop: '5px', fontSize: '0.85rem', color: 'var(--accent)' }}>{uploadMessage}</div>}
            </div>

            <div className="form-group">
              <label>Analyst Instructions</label>
              <textarea 
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
                disabled={status === 'pending' || status === 'running'}
                placeholder="e.g. Generate a pivot table showing total sales by region..."
              />
            </div>
            
            <button 
              type="submit" 
              className="action-btn" 
              disabled={status === 'pending' || status === 'running' || status === 'uploading' || !datasetPath}
            >
              {status === 'pending' ? 'Queued...' : status === 'running' ? 'Analyzing Data...' : 'Run Analysis'}
            </button>
            
            {status === 'running' && (
              <div style={{ marginTop: '15px', color: 'var(--text-secondary)', fontSize: '0.85rem', textAlign: 'center' }}>
                Task {taskId.substring(0,8)}... running in background.
              </div>
            )}
          </form>
        </div>
        
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="panel-title">Analytics Dashboard</h2>
          
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {images.length > 0 && (
              <div>
                <label style={{ color: 'var(--text-primary)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>BI Visualizations</label>
                <div className="image-grid">
                  {images.map((imgUrl, idx) => (
                    <img key={idx} src={imgUrl} alt={`Chart ${idx}`} />
                  ))}
                </div>
              </div>
            )}

            <div>
              <label style={{ color: 'var(--text-primary)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                Business Insights (Stdout)
              </label>
              <div className="terminal-output">
                {executionOutput || '> _'}
              </div>
            </div>

            <div>
              <label style={{ color: 'var(--text-primary)', fontWeight: 600, display: 'block', marginBottom: '8px' }}>
                Generated Pandas/SQL Code 
                <span style={{float:'right', color: status==='failed'?'red':status==='completed'?'#2563eb':status==='running'?'#f59e0b':''}}>
                  {status.toUpperCase()}
                </span>
              </label>
              <div className="code-output">
                {generatedCode || 'Awaiting instructions...'}
              </div>
            </div>
            
          </div>
        </div>
      </div>
    </main>
  );
}
