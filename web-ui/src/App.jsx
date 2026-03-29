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
    try {
      setLoading(true);
      const res = await fetch('/api/admin/unified-register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(unifiedForm)
      });
      if (res.ok) {
        alert("🎉 상품 및 진열 계획이 성공적으로 등록되었습니다!");
        setUnifiedForm({
          product_name: '', product_barcode: '', category: '과자',
          min_inventory_qty: 5, waypoint_name: '', slot_tag: '', row_num: 1
        });
        fetchStaticData();
      } else {
        const errData = await res.json();
        alert("❌ 등록 실패: " + errData.detail);
      }
    } catch (err) { alert("연결 오류 발생"); }
    finally { setLoading(false); }
  };

  const handleDeletePatrol = async (id) => {
    if (!window.confirm("정말 이 기록을 삭제하시겠습니까?")) return;
    try {
      const res = await fetch(`/api/patrol/${id}`, { method: 'DELETE' });
      if (res.ok) fetchGilbotData();
    } catch (err) { alert("삭제 실패"); }
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
        <div className="logo">🤖 GILBOT SERVER</div>
        <nav>
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>
            <span style={{marginRight: '8px'}}>📊</span> 대시보드
          </button>
          <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>
            <span style={{marginRight: '8px'}}>🛠️</span> 관리 대시보드
          </button>
          <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>
            <span style={{marginRight: '8px'}}>⚙️</span> 시스템 관리
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
                <div className="value" style={{color: alerts.length > 0 ? '#FF453A' : 'inherit'}}>{alerts.length} 건</div>
              </div>
              <div className="status-card">
                <h3>스캔 슬롯 (최근)</h3>
                <div className="value">{patrolList.length > 0 ? patrolList[0].scanned_slots : 0} 개</div>
              </div>
            </div>

            {/* 로봇 제어 센터 */}
            <div className="control-panel apple-card">
              <h2 className="section-title" style={{marginTop: 0}}>🎮 로봇 제어 센터</h2>
              <div style={{display: 'flex', gap: '15px'}}>
                <button className="apple-button secondary" 
                        onClick={handleFinishPatrol}
                        style={{flex: 1, height: '50px', fontSize: '16px'}}>🏠 기지로 복귀</button>
                <button className="apple-button" 
                        onClick={handleEmergencyStop}
                        style={{flex: 1, height: '50px', fontSize: '16px', background: '#FF453A'}}>🛑 비상 정지</button>
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
        ) : view === 'admin' ? (
          <div className="admin-dashboard">
            <header className="admin-header">
              <h1>⚙️ 통합 상품 및 진열 관리</h1>
              <p>상품 마스터 정보 및 데이터베이스 직접 제어</p>
            </header>

            <div className="admin-grid" style={{gridTemplateColumns: '1fr', gap: '20px'}}>
              {/* 상단: 통합 등록 폼 */}
              <section className="apple-card">
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
                  <h2 className="section-title" style={{margin: 0}}>✨ 통합 진열 상품 등록</h2>
                  <span className="tag info">One-Stop Manager</span>
                </div>
                
                <form onSubmit={handleUnifiedRegister}>
                  <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px'}}>
                    <div style={{background: 'rgba(0,0,0,0.02)', padding: '15px', borderRadius: '12px'}}>
                      <h3 style={{fontSize: '14px', marginBottom: '12px', opacity: 0.7}}>📦 상품 기본 정보</h3>
                      <div className="form-group">
                        <label>상품명</label>
                        <input type="text" placeholder="예: 신라면" value={unifiedForm.product_name} onChange={e => setUnifiedForm({...unifiedForm, product_name: e.target.value})} required />
                      </div>
                      <div className="form-group">
                        <label>상품 바코드 (Barcode)</label>
                        <input type="text" placeholder="상품에 인쇄된 바코드 입력" value={unifiedForm.product_barcode} onChange={e => setUnifiedForm({...unifiedForm, product_barcode: e.target.value})} required />
                      </div>
                      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px'}}>
                        <div className="form-group">
                          <label>카테고리</label>
                          <select value={unifiedForm.category} onChange={e => setUnifiedForm({...unifiedForm, category: e.target.value})}>
                            <option value="과자">과자</option>
                            <option value="음료">음료</option>
                            <option value="라면">라면</option>
                            <option value="기타">기타</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label>최소 수량 (목표)</label>
                          <input type="number" min="1" value={unifiedForm.min_inventory_qty} onChange={e => setUnifiedForm({...unifiedForm, min_inventory_qty: parseInt(e.target.value)})} />
                        </div>
                      </div>
                    </div>

                    <div style={{background: 'rgba(0, 122, 255, 0.03)', padding: '15px', borderRadius: '12px', border: '1px solid rgba(0, 122, 255, 0.1)'}}>
                      <h3 style={{fontSize: '14px', marginBottom: '12px', color: 'var(--accent-blue)'}}>📍 매대 위치 정보</h3>
                      <div className="form-group">
                        <label>위치/구역 이름 (Waypoint)</label>
                        <input 
                          type="text" 
                          list="waypoint-list"
                          placeholder="예: A구역 (신규 입력 시 자동 생성)" 
                          value={unifiedForm.waypoint_name} 
                          onChange={e => setUnifiedForm({...unifiedForm, waypoint_name: e.target.value})} 
                          required 
                        />
                        <datalist id="waypoint-list">
                          {waypoints.map(w => <option key={w.waypoint_id} value={w.waypoint_name} />)}
                        </datalist>
                      </div>
                      <div className="form-group">
                        <label>단 (Row)</label>
                        <input type="number" min="1" value={unifiedForm.row_num} onChange={e => setUnifiedForm({...unifiedForm, row_num: parseInt(e.target.value)})} />
                      </div>
                      <p style={{fontSize: '12px', color: '#8E8E93', marginTop: '10px'}}>※ 매대 태그는 상품 바코드를 그대로 사용합니다.</p>
                    </div>
                  </div>

                  <button type="submit" className="apple-button" style={{ width: '100%', marginTop: '20px', height: '48px', fontSize: '16px' }} disabled={loading}>
                    {loading ? '등록 중...' : '마스터 정보 및 진열 계획 등록'}
                  </button>
                </form>
              </section>

              {/* 하단 전체 폭: 상품 진열 계획 (Planogram) */}
              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>📋 상품 진열 계획 (Planogram) 조회</h2>
                <p style={{color: '#8E8E93', fontSize: '14px', marginBottom: '15px'}}>현재 로봇이 순찰하며 점검해야 할 마스터 진열 정보입니다.</p>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>위치(Waypoint)</th>
                        <th>단(Row)</th>
                        <th>진열 대상 상품</th>
                        <th>상품 바코드 (Shelf Tag)</th>
                      </tr>
                    </thead>
                  <tbody>
                    {(!patrolPlan || patrolPlan.length === 0) ? (
                      <tr><td colSpan="4" style={{textAlign: 'center', padding: '20px'}}>등록된 진열 계획이 없습니다.</td></tr>
                    ) : (
                      patrolPlan.map(plan => (
                        <tr key={plan.plan_id}>
                          <td><strong>{plan.waypoint_name}</strong></td>
                          <td>{plan.row_num || 1}단</td>
                          <td>{plan.product_name}</td>
                          <td><code>{plan.product_barcode}</code></td>
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
            <header>
              <h1>시스템 관리</h1>
              <p>순찰 기록 관리 및 시스템 무결성 작업</p>
            </header>

            <div className="admin-grid" style={{gridTemplateColumns: '1fr', gap: '20px'}}>
              <section className="apple-card">
                <h2 className="section-title" style={{marginTop: 0}}>⚙️ 순찰 시스템 설정</h2>
                {patrolConfigDraft && (
                <form onSubmit={handleUpdateConfig}>
                  <div className="form-group">
                    <label>회피 대기 시간 (초)</label>
                    <input type="number" 
                           value={patrolConfigDraft.avoidance_wait_time} 
                           onFocus={() => setIsEditingConfig(true)}
                           onChange={e => setPatrolConfigDraft({...patrolConfigDraft, avoidance_wait_time: parseInt(e.target.value)})} />
                  </div>
                  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
                    <div className="form-group">
                      <label>순찰 시작 가능 시각</label>
                      <input type="time" step="1" 
                             value={patrolConfigDraft.patrol_start_time} 
                             onFocus={() => setIsEditingConfig(true)}
                             onChange={e => setPatrolConfigDraft({...patrolConfigDraft, patrol_start_time: e.target.value})} />
                    </div>
                    <div className="form-group">
                      <label>순찰 종료/복귀 시각</label>
                      <input type="time" step="1" 
                             value={patrolConfigDraft.patrol_end_time} 
                             onFocus={() => setIsEditingConfig(true)}
                             onChange={e => setPatrolConfigDraft({...patrolConfigDraft, patrol_end_time: e.target.value})} />
                    </div>
                  </div>
                  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
                    <div className="form-group">
                      <label>반복 주기 (시간)</label>
                      <input type="number" min="0" max="23" 
                             value={patrolConfigDraft.interval_hour} 
                             onFocus={() => setIsEditingConfig(true)}
                             onChange={e => setPatrolConfigDraft({...patrolConfigDraft, interval_hour: parseInt(e.target.value)})} />
                    </div>
                    <div className="form-group">
                      <label>반복 주기 (분)</label>
                      <input type="number" min="0" max="59" 
                             value={patrolConfigDraft.interval_minute} 
                             onFocus={() => setIsEditingConfig(true)}
                             onChange={e => setPatrolConfigDraft({...patrolConfigDraft, interval_minute: parseInt(e.target.value)})} />
                    </div>
                  </div>
                  <div className="form-group" style={{flexDirection: 'row', alignItems: 'center', gap: '10px', marginTop: '10px'}}>
                    <input type="checkbox" 
                           checked={patrolConfigDraft.is_active} 
                           style={{width: 'auto'}}
                           onFocus={() => setIsEditingConfig(true)}
                           onChange={e => setPatrolConfigDraft({...patrolConfigDraft, is_active: e.target.checked})} />
                    <label style={{marginBottom: 0}}>순찰 활성화 상태</label>
                  </div>
                  <div style={{display: 'flex', gap: '10px', marginTop: '15px'}}>
                    <button type="submit" className="apple-button" style={{flex: 2}}>설정 값 저장하기</button>
                    {isEditingConfig && (
                      <button type="button" className="apple-button secondary" style={{flex: 1}} 
                              onClick={() => { setIsEditingConfig(false); setPatrolConfigDraft(patrolConfig); }}>취소</button>
                    )}
                  </div>
                </form>
                )}
              </section>

              <section className="apple-card">
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
        ) : (
          null
        )}
      </main>
    </div>
  )
}

export default App
