import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import Layout from '../components/Layout';
import Loader from '../components/Loader';
import { fetchCitizenRelationships } from '../services/citizenService';
import { formatError } from '../utils/formatError';
import '../styles/relationshipGraph.css';

const NODE_COLORS = {
  citizen: '#0b2545',
  mobile: '#c9a227',
  village: '#134074',
  district: '#1e5a8a',
  related_citizen: '#4b6a8a',
};

const NODE_SIZES = {
  citizen: 14,
  mobile: 9,
  village: 10,
  district: 10,
  related_citizen: 8,
};

function getNodeColor(node) {
  if (node.is_center) return NODE_COLORS.citizen;
  return NODE_COLORS[node.type] || '#6b7280';
}

function getNodeSize(node) {
  if (node.is_center) return NODE_SIZES.citizen;
  return NODE_SIZES[node.type] || 7;
}

export default function RelationshipGraph() {
  const { id } = useParams();
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const [graphMeta, setGraphMeta] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 800, height: 520 });

  const loadGraph = useCallback(async () => {
    if (!id) {
      setError('Invalid citizen ID');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await fetchCitizenRelationships(id);
      const graph = data.graph;
      if (!graph?.nodes?.length) {
        setError('No relationship data available');
        setGraphData({ nodes: [], links: [] });
        setGraphMeta(null);
        return;
      }
      setGraphMeta(graph);
      setGraphData({
        nodes: graph.nodes.map((n) => ({ ...n })),
        links: graph.links.map((l) => ({ ...l })),
      });
    } catch (err) {
      setError(formatError(err, 'Failed to load relationship graph'));
      setGraphData({ nodes: [], links: [] });
      setGraphMeta(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: Math.max(420, Math.min(560, window.innerHeight - 320)),
        });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  useEffect(() => {
    if (graphRef.current && graphData.nodes.length) {
      graphRef.current.zoomToFit(400, 60);
    }
  }, [graphData]);

  const legendItems = useMemo(
    () => [
      { type: 'citizen', label: 'Center citizen' },
      { type: 'mobile', label: 'Mobile' },
      { type: 'village', label: 'Village' },
      { type: 'district', label: 'District' },
      { type: 'related_citizen', label: 'Related record' },
    ],
    [],
  );

  const handleNodeClick = (node) => {
    if (node.type === 'related_citizen' && node.citizen_id) {
      navigate(`/person-profile/${node.citizen_id}`);
    }
  };

  const handleZoomIn = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() * 1.3, 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() / 1.3, 300);
    }
  };

  const handleFit = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 60);
    }
  };

  return (
    <Layout>
      {loading && <Loader label="Loading relationship graph..." />}

      <div className="relationship-graph-page">
        <nav className="graph-breadcrumb" aria-label="Breadcrumb">
          <Link to={`/person-profile/${id}`}>← Back to Person 360</Link>
          <span className="graph-breadcrumb-sep">/</span>
          <Link to="/citizens">Citizen records</Link>
        </nav>

        <header className="graph-header-card card">
          <div>
            <span className="graph-eyebrow">Intelligence network</span>
            <h1>Relationship graph</h1>
            <p>
              {graphMeta?.citizen_name
                ? `Connections for ${graphMeta.citizen_name}`
                : 'Citizen relationship visualization'}
            </p>
          </div>
          <span className="graph-header-badge">GPIP Graph v1</span>
        </header>

        {error && (
          <div className="alert alert-error">
            {error}
            <button
              type="button"
              className="btn btn-secondary graph-retry-btn"
              onClick={() => navigate(`/person-profile/${id}`)}
            >
              Return to profile
            </button>
          </div>
        )}

        {!loading && !error && graphData.nodes.length > 0 && (
          <>
            <div className="graph-legend card">
              {legendItems.map(({ type, label }) => (
                <span key={type} className="graph-legend-item">
                  <span
                    className="graph-legend-dot"
                    style={{ background: getNodeColor({ type, is_center: type === 'citizen' }) }}
                  />
                  {label}
                </span>
              ))}
              <span className="graph-legend-hint">Drag nodes · Scroll to zoom · Click related citizen to open profile</span>
            </div>

            <div className="graph-canvas-card card">
              <div className="graph-toolbar">
                <button type="button" className="btn btn-secondary graph-tool-btn" onClick={handleZoomIn}>
                  Zoom in
                </button>
                <button type="button" className="btn btn-secondary graph-tool-btn" onClick={handleZoomOut}>
                  Zoom out
                </button>
                <button type="button" className="btn btn-secondary graph-tool-btn" onClick={handleFit}>
                  Fit view
                </button>
              </div>
              <div ref={containerRef} className="graph-canvas-wrap">
                <ForceGraph2D
                  ref={graphRef}
                  width={dimensions.width}
                  height={dimensions.height}
                  graphData={graphData}
                  nodeLabel={(node) => `${node.label} (${node.type.replace('_', ' ')})`}
                  nodeColor={getNodeColor}
                  nodeVal={getNodeSize}
                  linkColor={() => 'rgba(19, 64, 116, 0.45)'}
                  linkWidth={1.5}
                  linkDirectionalArrowLength={5}
                  linkDirectionalArrowRelPos={1}
                  onNodeClick={handleNodeClick}
                  cooldownTicks={80}
                  d3AlphaDecay={0.02}
                  d3VelocityDecay={0.3}
                  backgroundColor="#f4f6f8"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
