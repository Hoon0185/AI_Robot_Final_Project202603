import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [status, setStatus] = useState({ status: 'offline', database: 'unknown' });
  const [patrolList, setPatrolList] = useState([]);
  const [loading, setLoading] = useState(false);

  // 백엔드(FastAPI)에서 데이터를 가져오는 함수
  const fetchGilbotData = async () => {
    try {
      setLoading(true);
      // 1. 서버 상태 가져오기
      const statusRes = await fetch('/api/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        // 데이터 구조가 올바른지 확인 후 업데이트
        setStatus({
          status: statusData.status || 'offline',
          database: statusData.database || 'unknown'
        });
      }

      // 2. 최근 순찰 로그 가져오기
      const patrolRes = await fetch('/api/patrol/list');
      if (patrolRes.ok) {
        const patrolData = await patrolRes.json();
        // 응답이 배열인지 확인 후 업데이트
        if (Array.isArray(patrolData)) {
          setPatrolList(patrolData);
        }
      }
    } catch (error) {
      console.error("연결 확인 실패 (서버가 아직 꺼져있을 수 있습니다):", error);
      // 에러 시 상태 초기화
      setStatus({ status: 'offline', database: 'unknown' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGilbotData();
    // 10초마다 자동으로 새로고침 (선택 사항)
    const timer = setInterval(fetchGilbotData, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="dashboard">
      <header>
        <h1>🤖 Gilbot Commander</h1>
        <p>전술 조종실 - 실시간 모니터링</p>
      </header>

      <section className="status-grid">
        <div className="card">
          <h3>서버 상태</h3>
          <p className={status.status === 'running' ? 'online' : 'offline'}>
            {(status.status || 'OFFLINE').toUpperCase()}
          </p>
        </div>
        <div className="card">
          <h3>DB 연결</h3>
          <p className={status.database === 'connected' ? 'online' : 'offline'}>
            {(status.database || 'UNKNOWN').toUpperCase()}
          </p>
        </div>
      </section>

      <section className="patrol-log">
        <h2>📋 최근 순찰 기록 (TOP 10)</h2>
        {loading && patrolList.length === 0 ? (
          <p>데이터 로딩 중...</p>
        ) : Array.isArray(patrolList) && patrolList.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>로봇</th>
                <th>위치</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {patrolList.map((log) => (
                <tr key={log.patrol_id}>
                  <td>{log.patrol_id}</td>
                  <td>{log.robot_id}</td>
                  <td>{log.location || 'N/A'}</td>
                  <td>{log.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="no-data">
            <p>데이터가 없거나 서버와 연결되지 않았습니다.</p>
            <p className="hint">(FastAPI 서버가 실행 중인지 확인하세요)</p>
          </div>
        )}
      </section>

      <p className="last-update">최지막 갱신: {new Date().toLocaleTimeString()}</p>
      <button className="refresh-btn" onClick={fetchGilbotData} disabled={loading}>
        {loading ? '갱신 중...' : '데이터 갱신'}
      </button>
    </div>
  )
}

export default App
