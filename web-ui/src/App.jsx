import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' or 'admin'
  const [status, setStatus] = useState({ status: 'offline', database: 'unknown' });
  const [patrolList, setPatrolList] = useState([]);
  const [products, setProducts] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [detections, setDetections] = useState([]);
  const [patrolPlan, setPatrolPlan] = useState([]);
  const [waypoints, setWaypoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newPlan, setNewPlan] = useState({ waypoint_id: '', barcode_tag: '', row_num: 1, product_id: '' });
  const [lastAlertCount, setLastAlertCount] = useState(0);
  const [showNotification, setShowNotification] = useState(false);

  // 알림 사운드 재생 함수 (내장 오디오 객체 사용)
  const playAlertSound = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();

      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);

      oscillator.start();
      oscillator.stop(audioCtx.currentTime + 0.5);
    } catch (e) {
      console.warn("Audio playback failed", e);
    }
  };
  const [patrolConfig, setPatrolConfig] = useState({
    avoidance_wait_time: 5,
    patrol_start_time: '09:00:00',
    patrol_end_time: '22:00:00',
    interval_hour: 1,
    interval_minute: 0,
    is_active: true
  });
  const [patrolConfigDraft, setPatrolConfigDraft] = useState(null);
  const [isEditingConfig, setIsEditingConfig] = useState(false);
  const [unifiedForm, setUnifiedForm] = useState({
    product_name: '',
    product_barcode: '',
    category: '과자',
    min_inventory_qty: 5,
    waypoint_name: '',
    row_num: 1
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [itemsPerPage, setItemsPerPage] = useState(5);
  const [currentPage, setCurrentPage] = useState(1);

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
        if (Array.isArray(alertData)) {
          // 새로운 알림이 발생했는지 체크
          if (alertData.length > lastAlertCount && lastAlertCount !== 0) {
            playAlertSound();
            setShowNotification(true);
            setTimeout(() => setShowNotification(false), 5000); // 5초 후 자동 닫힘
          }
          setAlerts(alertData);
          setLastAlertCount(alertData.length);
        }
      }

      // 3. 인식 로그 (Detection log)
      const detectionRes = await fetch('/api/detections');
      if (detectionRes.ok) {
        const detectionData = await detectionRes.json();
        if (Array.isArray(detectionData)) setDetections(detectionData);
      }

    } catch (error) {
      console.error("데이터 로딩 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStaticData = async () => {
    try {
      const configRes = await fetch('/api/patrol/config');
      if (configRes.ok) {
        const configData = await configRes.json();
        setPatrolConfig(configData);
        setPatrolConfigDraft(configData);
        setIsEditingConfig(false);
      }
      const productRes = await fetch('/api/products');
      if (productRes.ok) {
        const productData = await productRes.json();
        if (Array.isArray(productData)) setProducts(productData);
      }
      const planRes = await fetch('/api/patrol/plan');
      if (planRes.ok) {
        const planData = await planRes.json();
        if (Array.isArray(planData)) setPatrolPlan(planData);
      }
      const waypointRes = await fetch('/api/waypoints');
      if (waypointRes.ok) {
        const waypointData = await waypointRes.json();
        if (Array.isArray(waypointData)) setWaypoints(waypointData);
      }
    } catch (error) {
      console.error("데이터(정적) 로컬 로딩 실패:", error);
    }
  };

  useEffect(() => {
    fetchStaticData();
    fetchGilbotData();
  }, []);

  // 대시보드일 때만 3초마다 새로고침 (실시간 감시용)
  useEffect(() => {
    if (view === 'dashboard') {
      const interval = setInterval(fetchGilbotData, 3000);
      return () => clearInterval(interval);
    }
  }, [view]);

  // 주기적으로 전체 데이터 갱신 (더 느린 주기로, 예를 들어 1분마다)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStaticData();
      fetchGilbotData();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // --- Admin Functions ---
  const handleUnifiedRegister = async (e) => {
    e.preventDefault();
    if (!unifiedForm.product_name || !unifiedForm.product_barcode || !unifiedForm.waypoint_name) {
      alert("⚠️ 필수 항목들을 모두 입력해 주세요.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/admin/unified-register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(unifiedForm)
      });
      if (res.ok) {
        alert("✅ 상품 및 위치 정보가 성공적으로 등록/수정되었습니다!");
        fetchStaticData();
        fetchGilbotData();
      } else {
        const errData = await res.json();
        alert("❌ 처리 실패: " + errData.detail);
      }
    } catch (err) { alert("연결 오류 발생"); }
    finally { setLoading(false); }
  };

  const handleEditClick = (plan) => {
    setUnifiedForm({
      product_name: plan.product_name,
      product_barcode: plan.product_barcode,
      category: plan.category || '과자',
      min_inventory_qty: plan.min_inventory_qty || 5,
      waypoint_name: plan.waypoint_name,
      row_num: plan.row_num || 1
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleDeletePatrol = async (id) => {
    if (!window.confirm("정말 이 기록을 삭제하시겠습니까?")) return;
    try {
      const res = await fetch(`/api/patrol/${id}`, { method: 'DELETE' });
      if (res.ok) fetchGilbotData();
    } catch (err) { alert("삭제 실패"); }
  };

  const handleDeletePlan = async (id) => {
    if (!window.confirm("정말 이 순찰 계획을 삭제하시겠습니까?")) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/patrol/plan/${id}`, { method: 'DELETE' });
      if (res.ok) {
        alert("순찰 계획이 삭제되었습니다.");
        fetchStaticData();
      } else {
        throw new Error("삭제 실패");
      }
    } catch (err) {
      alert("삭제 실패: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateConfig = async (e) => {
    if (e) e.preventDefault();
    try {
      const res = await fetch('/api/patrol/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patrolConfigDraft)
      });
      if (res.ok) {
        alert("순찰 설정이 저장되었습니다.");
        fetchStaticData(); // 저장 성공 시에만 최신 데이터 다시 가져옴
      }
    } catch (err) { alert("설정 저장 실패"); }
  };

  const handleFinishPatrol = async () => {
    if (!window.confirm("순찰을 마치고 복귀하시겠습니까? (5초 후 완료)")) return;
    try {
      setTimeout(async () => {
        const res = await fetch('/api/patrol/finish', { method: 'POST' });
        if (res.ok) {
          alert("성공적으로 복귀 완료되었습니다.");
          fetchGilbotData();
        } else { alert("복귀 실패 (진행중인 순찰 없음)"); }
      }, 5000);
    } catch (err) { alert("연결 오류"); }
  };

  const handleEmergencyStop = async () => {
    if (!window.confirm("🚨 비상 정지 하시겠습니까?")) return;
    try {
      const res = await fetch('/api/patrol/stop', { method: 'POST' });
      if (res.ok) {
        alert("순찰이 즉시 중단되었습니다.");
        fetchGilbotData();
      }
    } catch (err) { alert("명령 전달 실패"); }
  };

  const handleStorePlan = async (e) => {
    e.preventDefault();
    if (!newPlan.waypoint_id || !newPlan.product_id || !newPlan.barcode_tag) {
      alert("모든 필드를 입력해 주세요.");
      return;
    }
    try {
      const res = await fetch('/api/patrol/plan/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPlan)
      });
      if (res.ok) {
        alert("진열 계획이 성공적으로 등록되었습니다.");
        setNewPlan({ waypoint_id: '', barcode_tag: '', row_num: 1, product_id: '' });
        fetchStaticData();
      }
    } catch (err) { alert("계획 등록 실패"); }
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <header className="sidebar-header">
          <div className="logo-container">
            <div className="logo">GILBOT</div>
            <div className="logo-sub">당신의 길 벗</div>
          </div>
        </header>

        <div style={{ padding: '0 8px', marginTop: '20px' }}>
          <div className="status-indicator">
            <span className={`dot ${status.status === 'running' || status.status === 'online' ? 'online' : 'offline'}`}></span>
            <div>
              <div style={{ fontWeight: '600', fontSize: '13px' }}>Robot {status.status === 'running' || status.status === 'online' ? 'Online' : 'Offline'}</div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>DB: {status.database}</div>
            </div>
          </div>
        </div>
      </aside>

      <main className="content">
        {view === 'dashboard' ? (
          <div className="dashboard-content">
            <header className="content-header">
              <div className="title-section">
                <h1>관제상황판</h1>
                <p>실시간 패트롤 결과 및 이상 탐지 현황</p>
              </div>
              <div className="segmented-control">
                <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>대시보드</button>
                <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>상품/위치 관리</button>
                <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>시스템</button>
              </div>
            </header>

            {/* 실시간 알림 배너 */}
            {showNotification && (
              <div className="notification-banner anomaly">
                <div className="notif-icon">🚨</div>
                <div className="notif-body">
                  <strong>새로운 이상 탐지!</strong>
                  <span>매대 점검이 필요한 항목이 발견되었습니다.</span>
                </div>
                <button onClick={() => setShowNotification(false)}>×</button>
              </div>
            )}

            <div className="status-grid">
              <div className="status-card">
                <h3>순찰 회차</h3>
                <div className="value">{patrolList.length > 0 ? `#${patrolList[0].patrol_id}` : '-'} 회</div>
              </div>
              <div className="status-card">
                <h3>미해결 알림</h3>
                <div className="value" style={{ color: alerts.length > 0 ? '#FF453A' : 'inherit' }}>{alerts.length} 건</div>
              </div>
              <div className="status-card">
                <h3>스캔 슬롯 (최근)</h3>
                <div className="value">{patrolList.length > 0 ? patrolList[0].scanned_slots : 0} 개</div>
              </div>
            </div>

            {/* 로봇 제어 센터 */}
            <div className="control-panel apple-card">
              <h2 className="section-title" style={{ marginTop: 0 }}>🎮 로봇 제어 센터</h2>
              <div style={{ display: 'flex', gap: '15px' }}>
                <button className="apple-button secondary"
                  onClick={handleFinishPatrol}
                  style={{ flex: 1, height: '50px', fontSize: '16px' }}>🏠 기지로 복귀</button>
                <button className="apple-button"
                  onClick={handleEmergencyStop}
                  style={{ flex: 1, height: '50px', fontSize: '16px', background: '#FF453A' }}>🛑 비상 정지</button>
              </div>
            </div>

            <div className="dashboard-grid">
              {/* 왼쪽: Patrol Log */}
              <section className="apple-card">
                <h2 className="section-title" style={{ marginTop: 0 }}>📋 최근 순찰 기록</h2>
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
                          <td><span style={{ color: log.error_found > 0 ? '#FF453A' : 'inherit' }}>{log.error_found}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* 오른쪽: 실시간 알림 */}
              <section className="apple-card">
                <h2 className="section-title" style={{ marginTop: 0 }}>🚨 긴급 알림</h2>
                <div className="alert-list">
                  {alerts.length === 0 ? <p style={{ color: '#8E8E93', textAlign: 'center', padding: '20px' }}>현재 발견된 이상이 없습니다.</p> :
                    alerts.slice(0, 5).map(alert => (
                      <div key={alert.alert_id} className="alert-item">
                        <div className="alert-content">
                          <h4>{alert.alert_type} 감지</h4>
                          <p>{alert.waypoint_name || '매대'} - {alert.product_name || '상품미확인'}</p>
                        </div>
                        <span className="tag" style={{ background: 'rgba(255, 69, 58, 0.2)', color: '#FF453A' }}>미처리</span>
                      </div>
                    ))
                  }
                </div>
                {alerts.length > 5 && <p style={{ fontSize: '12px', textAlign: 'right', marginTop: '10px', color: '#8E8E93' }}>그외 {alerts.length - 5}건 더 있음...</p>}
              </section>

              {/* 하단: 전체 폭 Recognition Log */}
              <section className="apple-card" style={{ gridColumn: '1 / -1' }}>
                <h2 className="section-title" style={{ marginTop: 0 }}>🔍 실시간 인식 로그 (Detection)</h2>
                <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
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
                          <td style={{ fontSize: '12px', color: '#8E8E93' }}>{d.odom_x?.toFixed(2)}, {d.odom_y?.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        ) : view === 'admin' ? (
          <div className="admin-dashboard">
            <header className="content-header">
              <div className="title-section">
                <h1>상품 위치 관리</h1>
                <p>이미 등록된 마스터 상품 정보를 찾아서 원하는 웨이포인트(구역)에 할당합니다.</p>
              </div>
              <div className="segmented-control">
                <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>대시보드</button>
                <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>상품/위치 관리</button>
                <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>시스템</button>
              </div>
            </header>

            <div className="admin-grid-unified">
              <section className="unified-manager">
                {/* 1. 왼쪽 슬림 사이드바: 상품 마스터 목록 */}
                <div className="unified-sidebar">
                  <h3 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px' }}>📦 마스터 상품 선택</h3>
                  <div className="form-group" style={{ marginBottom: '16px' }}>
                    <input
                      type="text"
                      placeholder="상품명/바코드 검색..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>

                  <div className="table-container" style={{ maxHeight: '440px', overflowY: 'auto', border: 'none', background: 'transparent' }}>
                    <table className="selectable-table slim">
                      <thead>
                        <tr><th>상품명</th><th>바코드</th></tr>
                      </thead>
                      <tbody>
                        {products
                          .filter(p => !searchTerm || p.product_name.toLowerCase().includes(searchTerm.toLowerCase()) || p.barcode.includes(searchTerm))
                          .map(p => (
                            <tr key={p.product_id}
                              onClick={() => setUnifiedForm({ ...unifiedForm, product_name: p.product_name, product_barcode: p.barcode, category: p.category || '기타' })}
                              className={unifiedForm.product_barcode === p.barcode ? 'selected-row' : ''}>
                              <td style={{ fontSize: '13px' }}>{p.product_name}</td>
                              <td style={{ fontSize: '12px' }}><code>{p.barcode}</code></td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 중앙 구분선 */}
                <div className="unified-divider"></div>

                {/* 2. 오른쪽 메인: 상세 연결 설정 */}
                <div className="unified-content">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                    <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '700' }}>📍 상품 위치 매핑 관리</h2>
                    {unifiedForm.product_barcode && <span className="tag 완료">상품 선택됨</span>}
                  </div>

                  <form onSubmit={handleUnifiedRegister}>
                    <div style={{ background: 'rgba(10, 132, 255, 0.05)', padding: '24px', borderRadius: '16px', marginBottom: '32px', border: '1px solid rgba(10, 132, 255, 0.2)' }}>
                      <h3 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '12px', color: 'var(--accent-blue)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Selected Product</h3>
                      {unifiedForm.product_barcode ? (
                        <div>
                          <div style={{ fontSize: '28px', fontWeight: '800', marginBottom: '8px', letterSpacing: '-0.02em' }}>{unifiedForm.product_name}</div>
                          <div style={{ fontSize: '16px', color: 'var(--text-secondary)' }}>
                            바코드 <code>{unifiedForm.product_barcode}</code> | 카테고리 <strong>{unifiedForm.category}</strong>
                          </div>
                        </div>
                      ) : (
                        <div style={{ color: 'var(--text-secondary)', fontSize: '18px', fontStyle: 'italic', padding: '20px 0', textAlign: 'center' }}>
                          왼쪽 목록에서 연결할 마스터 상품을 먼저 선택하세요.
                        </div>
                      )}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                      <div className="form-group">
                        <label>웨이포인트 (Waypoint)</label>
                        <input
                          type="text"
                          list="waypoint-list"
                          placeholder="구역 또는 웨이포인트 이름"
                          value={unifiedForm.waypoint_name}
                          onChange={e => setUnifiedForm({ ...unifiedForm, waypoint_name: e.target.value })}
                          disabled={!unifiedForm.product_barcode}
                          required
                        />
                        <datalist id="waypoint-list">
                          {waypoints.map(w => <option key={w.waypoint_id} value={w.waypoint_name} />)}
                        </datalist>
                      </div>

                      <div className="form-group">
                        <label>진열 단 (Shelf Level)</label>
                        <input
                          type="number" min="1"
                          value={unifiedForm.row_num}
                          onChange={e => setUnifiedForm({ ...unifiedForm, row_num: parseInt(e.target.value) })}
                          disabled={!unifiedForm.product_barcode}
                        />
                      </div>
                    </div>

                    <div style={{ marginTop: 'auto', paddingTop: '24px', display: 'flex', gap: '16px' }}>
                      <button type="submit" className="apple-button" style={{ flex: 2, height: '54px', fontSize: '16px' }} disabled={!unifiedForm.product_barcode || loading}>
                        {loading ? '연결 처리 중...' : '선택한 상품을 이 위치에 연결하기'}
                      </button>
                      {unifiedForm.product_barcode && (
                        <button type="button" className="apple-button secondary"
                          style={{ flex: 1, height: '54px' }}
                          onClick={() => setUnifiedForm({ product_name: '', product_barcode: '', category: '과자', min_inventory_qty: 5, waypoint_name: '', row_num: 1 })}>
                          재선택
                        </button>
                      )}
                    </div>
                  </form>
                </div>
              </section>

              {/* 하단 전체 폭: 현재 등록된 상품 및 순찰 순서 관리 */}
              <section className="apple-card" style={{ gridColumn: '1 / -1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                  <div>
                    <h2 className="section-title" style={{ margin: 0 }}>📋 순찰 제품 및 경로 시퀀스 관리</h2>
                    <p style={{ color: '#86868B', fontSize: '14px', marginTop: '4px' }}>로봇이 방문할 상품 태그 순서를 화살표 버튼으로 조정하세요.</p>
                  </div>
                  <div className="tag 완료">실시간 정렬됨</div>
                </div>

                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: '100px', textAlign: 'center' }}>순찰 순서</th>
                        <th>상품명 / 바코드</th>
                        <th>부착 위치(웨이포인트)</th>
                        <th>진열 단</th>
                        <th style={{ width: '150px', textAlign: 'center' }}>순서 조정</th>
                        <th style={{ width: '80px' }}>관리</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(!patrolPlan || patrolPlan.length === 0) ? (
                        <tr><td colSpan="6" style={{ textAlign: 'center', padding: '30px', color: '#8E8E93' }}>등록된 제품 위치 정보가 없습니다. 상단에서 연동해 주세요.</td></tr>
                      ) : (
                        patrolPlan.map((plan, index) => (
                          <tr key={plan.plan_id}>
                            <td style={{ textAlign: 'center' }}>
                              <span style={{ background: '#007AFF', color: 'white', padding: '4px 10px', borderRadius: '12px', fontSize: '13px', fontWeight: 'bold' }}>
                                #{index + 1}
                              </span>
                            </td>
                            <td>
                              <div style={{ fontWeight: '600', fontSize: '15px' }}>{plan.product_name}</div>
                              <div style={{ fontSize: '12px', color: '#86868B' }}><code>{plan.product_barcode}</code></div>
                            </td>
                            <td>
                              <span className="tag info">{plan.waypoint_name}</span>
                            </td>
                            <td>{plan.row_num || 1}단</td>
                            <td style={{ textAlign: 'center' }}>
                              <div className="reorder-controls" style={{ justifyContent: 'center' }}>
                                <button className="ghost-btn"
                                  disabled={index === 0 || loading}
                                  onClick={async () => {
                                    const orders = patrolPlan.map((p, idx) => {
                                      if (idx === index) return { plan_id: p.plan_id, plan_order: index - 1 };
                                      if (idx === index - 1) return { plan_id: p.plan_id, plan_order: index };
                                      return { plan_id: p.plan_id, plan_order: idx };
                                    });
                                    try {
                                      setLoading(true);
                                      const res = await fetch('/api/patrol/plan/order', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify(orders)
                                      });
                                      if (!res.ok) throw new Error("Update failed");
                                      await fetchStaticData();
                                    } catch (e) {
                                      alert("순서 변경 실패: " + e.message);
                                    } finally {
                                      setLoading(false);
                                    }
                                  }}>▲</button>
                                <button className="ghost-btn"
                                  disabled={index === patrolPlan.length - 1 || loading}
                                  onClick={async () => {
                                    const orders = patrolPlan.map((p, idx) => {
                                      if (idx === index) return { plan_id: p.plan_id, plan_order: index + 1 };
                                      if (idx === index + 1) return { plan_id: p.plan_id, plan_order: index };
                                      return { plan_id: p.plan_id, plan_order: idx };
                                    });
                                    try {
                                      setLoading(true);
                                      const res = await fetch('/api/patrol/plan/order', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify(orders)
                                      });
                                      if (!res.ok) throw new Error("Update failed");
                                      await fetchStaticData();
                                    } catch (e) {
                                      alert("순서 변경 실패: " + e.message);
                                    } finally {
                                      setLoading(false);
                                    }
                                  }}>▼</button>
                              </div>
                            </td>
                            <td>
                              <div style={{ display: 'flex', gap: '8px' }}>
                                <button className="apple-button secondary"
                                  style={{ padding: '6px 12px', fontSize: '12px' }}
                                  onClick={() => handleEditClick(plan)}>
                                  수정
                                </button>
                                <button className="apple-button secondary"
                                  style={{ padding: '6px 12px', fontSize: '12px', color: '#FF453A' }}
                                  onClick={() => handleDeletePlan(plan.plan_id)}>
                                  삭제
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        ) : view === 'system' ? (
          /* System View */
          <div className="system-content">
            <header className="content-header">
              <div className="title-section">
                <h1>시스템 관리</h1>
                <p>순찰 기록 관리 및 시스템 무결성 작업</p>
              </div>
              <div className="segmented-control">
                <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>대시보드</button>
                <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>상품/위치 관리</button>
                <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>시스템</button>
              </div>
            </header>

            <div className="admin-grid" style={{ gridTemplateColumns: '1fr', gap: '20px' }}>
              <section className="apple-card">
                <h2 className="section-title" style={{ marginTop: 0 }}>⚙️ 순찰 시스템 설정</h2>
                {patrolConfigDraft && (
                  <form onSubmit={handleUpdateConfig}>
                    <div className="form-group">
                      <label>회피 대기 시간 (초)</label>
                      <input type="number"
                        value={patrolConfigDraft.avoidance_wait_time}
                        onFocus={() => setIsEditingConfig(true)}
                        onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, avoidance_wait_time: parseInt(e.target.value) })} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                      <div className="form-group">
                        <label>순찰 시작 가능 시각</label>
                        <input type="time" step="1"
                          value={patrolConfigDraft.patrol_start_time}
                          onFocus={() => setIsEditingConfig(true)}
                          onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, patrol_start_time: e.target.value })} />
                      </div>
                      <div className="form-group">
                        <label>순찰 종료/복귀 시각</label>
                        <input type="time" step="1"
                          value={patrolConfigDraft.patrol_end_time}
                          onFocus={() => setIsEditingConfig(true)}
                          onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, patrol_end_time: e.target.value })} />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                      <div className="form-group">
                        <label>반복 주기 (시간)</label>
                        <input type="number" min="0" max="23"
                          value={patrolConfigDraft.interval_hour}
                          onFocus={() => setIsEditingConfig(true)}
                          onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, interval_hour: parseInt(e.target.value) })} />
                      </div>
                      <div className="form-group">
                        <label>반복 주기 (분)</label>
                        <input type="number" min="0" max="59"
                          value={patrolConfigDraft.interval_minute}
                          onFocus={() => setIsEditingConfig(true)}
                          onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, interval_minute: parseInt(e.target.value) })} />
                      </div>
                    </div>
                    <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '10px', marginTop: '10px' }}>
                      <input type="checkbox"
                        checked={patrolConfigDraft.is_active}
                        style={{ width: 'auto' }}
                        onFocus={() => setIsEditingConfig(true)}
                        onChange={e => setPatrolConfigDraft({ ...patrolConfigDraft, is_active: e.target.checked })} />
                      <label style={{ marginBottom: 0 }}>순찰 활성화 상태</label>
                    </div>
                    <div style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
                      <button type="submit" className="apple-button" style={{ flex: 2 }}>설정 값 저장하기</button>
                      {isEditingConfig && (
                        <button type="button" className="apple-button secondary" style={{ flex: 1 }}
                          onClick={() => { setIsEditingConfig(false); setPatrolConfigDraft(patrolConfig); }}>취소</button>
                      )}
                    </div>
                  </form>
                )}
              </section>

              <section className="apple-card">
                <h2 className="section-title" style={{ marginTop: 0 }}>⚙️ 시스템 작업 로그 관리</h2>
                <p style={{ color: '#8E8E93', fontSize: '14px', marginBottom: '20px' }}>순찰 기록의 무결성을 위해 필요한 경우 기록을 삭제할 수 있습니다.</p>
                <div className="table-container">
                  <table className="fixed-table">
                    <thead>
                      <tr>
                        <th style={{ width: '80px' }}>ID</th>
                        <th>시작 시간</th>
                        <th style={{ width: '120px' }}>상태</th>
                        <th style={{ width: '120px' }}>스캔</th>
                        <th style={{ width: '100px' }}>조치</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patrolList.map(log => (
                        <tr key={log.patrol_id}>
                          <td style={{ fontWeight: '600' }}>#{log.patrol_id}</td>
                          <td style={{ color: '#424245' }}>{new Date(log.start_time).toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                          <td style={{ color: log.status === '완료' ? 'var(--accent-green)' : 'var(--text-primary)' }}>{log.status}</td>
                          <td>{log.scanned_slots} 슬롯</td>
                          <td>
                            <button className="apple-button secondary" style={{ padding: '6px 12px', fontSize: '13px', color: '#FF453A', borderRadius: '8px' }}
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
        ) : (
          null
        )}
      </main>
    </div>
  )
}

export default App
