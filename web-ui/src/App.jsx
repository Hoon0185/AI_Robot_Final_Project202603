import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' or 'admin'
  const [status, setStatus] = useState({ status: 'offline', database: 'unknown' });
  const [patrolList, setPatrolList] = useState([]);
  const [products, setProducts] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(false);

  // 입력을 위한 폼 상태 (상품 마스터 관리용)
  const [newProduct, setNewProduct] = useState({ product_name: '', barcode: '', standard_qty: 0, category: 'Snack' });

  const fetchGilbotData = async () => {
    try {
      setLoading(true);
      const statusRes = await fetch('/api/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus({
          status: statusData.status || 'offline',
          database: statusData.database || 'unknown'
        });
      }

      // 1. 순찰 기록 (Patrol Log)
      const patrolRes = await fetch('/api/patrol/list');
      if (patrolRes.ok) {
        const patrolData = await patrolRes.json();
        if (Array.isArray(patrolData)) setPatrolList(patrolData);
      }

      // 2. 알람 내역 (Alerts)
      const alertRes = await fetch('/api/alerts');
      if (alertRes.ok) {
        const alertData = await alertRes.json();
        if (Array.isArray(alertData)) setAlerts(alertData);
      }

      // 3. 인식 로그 (Detection log)
      const detectionRes = await fetch('/api/detections');
      if (detectionRes.ok) {
        const detectionData = await detectionRes.json();
        if (Array.isArray(detectionData)) setDetections(detectionData);
      }

      // 4. 상품 마스터 (Admin용)
      const productRes = await fetch('/api/products');
      if (productRes.ok) {
        const productData = await productRes.json();
        if (Array.isArray(productData)) setProducts(productData);
      }

    } catch (error) {
      console.error("데이터 로딩 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGilbotData();
    const timer = setInterval(fetchGilbotData, 10000); // 10초마다 자동 갱신
    return () => clearInterval(timer);
  }, []);

  // --- Admin Functions ---
  const handleAddProduct = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/products/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProduct)
      });
      if (res.ok) {
        alert("상품 등록 완료!");
        setNewProduct({ product_name: '', barcode: '', standard_qty: 0, category: 'Snack' });
        fetchGilbotData();
      }
    } catch (err) { alert("등록 실패"); }
  };

  const handleDeletePatrol = async (id) => {
    if (!window.confirm("정말 이 기록을 삭제하시겠습니까?")) return;
    try {
      const res = await fetch(`/api/patrol/${id}`, { method: 'DELETE' });
      if (res.ok) fetchGilbotData();
    } catch (err) { alert("삭제 실패"); }
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="logo">🤖 GILBOT SERVER</div>
        <nav>
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>
            <span style={{marginRight: '8px'}}>📊</span> 대시보드
          </button>
          <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>
            <span style={{marginRight: '8px'}}>🛠️</span> 관리 대시보드
          </button>
        </nav>
        
        <div className="status-indicator">
          <span className={`dot ${status.status === 'running' ? 'online' : 'offline'}`}></span>
          <span style={{fontSize: '12px', opacity: 0.8}}>{status.status.toUpperCase()} (DB: {status.database})</span>
        </div>
      </aside>

      <main className="content">
        {view === 'dashboard' ? (
          <div className="dashboard-content">
            <header>
              <h1>관제 상황판</h1>
              <p>실시간 패트롤 결과 및 이상 탐지 현황</p>
            </header>

            <div className="status-grid">
              <div className="status-card">
                <h3>순찰 회차</h3>
                <div className="value">{patrolList.length > 0 ? `#${patrolList[0].patrol_id}` : '-'} 회</div>
              </div>
              <div className="status-card">
                <h3>미해결 알림</h3>
                <div className="value" style={{color: alerts.length > 0 ? '#FF453A' : 'inherit'}}>{alerts.length} 건</div>
              </div>
              <div className="status-card">
                <h3>스캔 슬롯 (최근)</h3>
                <div className="value">{patrolList.length > 0 ? patrolList[0].scanned_slots : 0} 개</div>
              </div>
            </div>

            <div className="dashboard-grid">
              {/* 왼쪽: Patrol Log */}
              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>📋 최근 순찰 기록</h2>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>시간</th>
                        <th>상태</th>
                        <th>스캔수</th>
                        <th>오류</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patrolList.map(log => (
                        <tr key={log.patrol_id}>
                          <td>{log.patrol_id}</td>
                          <td>{new Date(log.start_time).toLocaleString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit' })}</td>
                          <td><span className={`tag ${log.status}`}>{log.status}</span></td>
                          <td>{log.scanned_slots}</td>
                          <td><span style={{color: log.error_found > 0 ? '#FF453A' : 'inherit'}}>{log.error_found}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* 오른쪽: 실시간 알림 */}
              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>🚨 긴급 알림</h2>
                <div className="alert-list">
                  {alerts.length === 0 ? <p style={{color: '#8E8E93', textAlign: 'center', padding: '20px'}}>현재 발견된 이상이 없습니다.</p> : 
                    alerts.slice(0, 5).map(alert => (
                      <div key={alert.alert_id} className="alert-item">
                        <div className="alert-content">
                          <h4>{alert.alert_type} 감지</h4>
                          <p>{alert.waypoint_name || '매대'} - {alert.product_name || '상품미확인'}</p>
                        </div>
                        <span className="tag" style={{background: 'rgba(255, 69, 58, 0.2)', color: '#FF453A'}}>미처리</span>
                      </div>
                    ))
                  }
                </div>
                {alerts.length > 5 && <p style={{fontSize: '12px', textAlign: 'right', marginTop: '10px', color: '#8E8E93'}}>그외 {alerts.length - 5}건 더 있음...</p>}
              </section>

              {/* 하단: 전체 폭 Recognition Log */}
              <section className="apple-card" style={{gridColumn: '1 / -1'}}>
                <h2 className="section-title" style={{marginTop: 0}}>🔍 실시간 인식 로그 (Detection)</h2>
                <div className="table-container" style={{maxHeight: '400px', overflowY: 'auto'}}>
                  <table>
                    <thead>
                      <tr>
                        <th>시간</th>
                        <th>ID</th>
                        <th>내용</th>
                        <th>결과</th>
                        <th>신뢰도</th>
                        <th>좌표(X,Y)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detections.map(d => (
                        <tr key={d.log_id}>
                          <td>{new Date(d.log_id * 1000).toLocaleTimeString()}</td>
                          <td><code>{d.tag_barcode}</code></td>
                          <td>{d.product_name || d.detected_barcode}</td>
                          <td><span className={`tag ${d.result}`}>{d.result}</span></td>
                          <td>{(d.confidence * 100).toFixed(0)}%</td>
                          <td style={{fontSize: '12px', color: '#8E8E93'}}>{d.odom_x?.toFixed(2)}, {d.odom_y?.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        ) : (
          /* Admin View */
          <div className="admin-content">
            <header>
              <h1>데이터 본부</h1>
              <p>상품 마스터 정보 및 데이터베이스 직접 제어</p>
            </header>

            <div className="admin-grid">
              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>📦 새 상품 등록</h2>
                <form onSubmit={handleAddProduct}>
                  <div className="form-group">
                    <label>상품명</label>
                    <input type="text" placeholder="예: 신라면" value={newProduct.product_name} onChange={e => setNewProduct({...newProduct, product_name: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>바코드</label>
                    <input type="text" placeholder="barcode string" value={newProduct.barcode} onChange={e => setNewProduct({...newProduct, barcode: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label>표준 재고 수량</label>
                    <input type="number" value={newProduct.standard_qty} onChange={e => setNewProduct({...newProduct, standard_qty: parseInt(e.target.value)})} required />
                  </div>
                  <button type="submit" className="apple-button">마스터 DB에 등록</button>
                </form>

                <div style={{marginTop: '40px', paddingTop: '20px', borderTop: '1px solid var(--border-color)'}}>
                  <h3 style={{fontSize: '15px', color: 'var(--accent-blue)'}}>🗄️ 고급 DB 관리</h3>
                  <a href="http://16.184.56.119/phpmyadmin" target="_blank" rel="noreferrer" className="phpmyadmin-link">
                    → phpMyAdmin으로 이동하여 직접 쿼리 실행
                  </a>
                </div>
              </section>

              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>🍭 등록 상품 조회</h2>
                <div className="table-container" style={{maxHeight: '500px', overflowY: 'auto'}}>
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>이름</th>
                        <th>바코드</th>
                        <th>분류</th>
                      </tr>
                    </thead>
                    <tbody>
                      {products.map(p => (
                        <tr key={p.product_id}>
                          <td>{p.product_id}</td>
                          <td>{p.product_name}</td>
                          <td><code>{p.barcode}</code></td>
                          <td>{p.category}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="apple-card" style={{gridColumn: '1 / -1'}}>
                <h2 className="section-title" style={{marginTop: 0}}>⚙️ 시스템 작업 로그 관리</h2>
                <p style={{color: '#8E8E93', fontSize: '14px', marginBottom: '20px'}}>순찰 기록의 무결성을 위해 필요한 경우 기록을 삭제할 수 있습니다.</p>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>시작 시간</th>
                        <th>상태</th>
                        <th>스캔</th>
                        <th>조치</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patrolList.map(log => (
                        <tr key={log.patrol_id}>
                          <td>{log.patrol_id}</td>
                          <td>{new Date(log.start_time).toLocaleString()}</td>
                          <td>{log.status}</td>
                          <td>{log.scanned_slots} 슬롯</td>
                          <td>
                            <button className="apple-button secondary" style={{padding: '6px 12px', fontSize: '13px', color: '#FF453A'}} 
                                    onClick={() => handleDeletePatrol(log.patrol_id)}>삭제</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
