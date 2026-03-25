import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [status, setStatus] = useState({ status: 'offline', database: 'unknown' });
  const [patrolList, setPatrolList] = useState([]);
  const [loading, setLoading] = useState(true);

  // 백엔드(FastAPI)에서 데이터를 가져오는 함수
  const fetchGilbotData = async () => {
    try {
      setLoading(true);
      // 1. 서버 상태 가져오기 (FastAPI 8000 포트로 전화 걸기!)
      const statusRes = await fetch('/api/status');
      const statusData = await statusRes.json();
      setStatus(statusData);

      // 2. 최근 순찰 로그 가져오기
      const patrolRes = await fetch('/api/patrol/list');
      const patrolData = await patrolRes.json();
      setPatrolList(patrolData);
    } catch (error) {
      console.error("데이터를 가져오는데 실패했습니다:", error);
    } finally {
      setLoading(false);
    }
  };

  // 컴포넌트가 처음 나타날 때 실행!
  useEffect(() => {
    fetchGilbotData();
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
            {status.status.toUpperCase()}
          </p>
        </div>
        <div className="card">
          <h3>DB 연결</h3>
          <p className={status.database === 'connected' ? 'online' : 'offline'}>
            {status.database.toUpperCase()}
          </p>
        </div>
      </section>

      <section className="patrol-log">
        <h2>📋 최근 순찰 기록 (TOP 10)</h2>
        {loading ? (
          <p>데이터 로딩 중...</p>
        ) : (
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
        )}
      </section>

      <button className="refresh-btn" onClick={fetchGilbotData}>
        데이터 갱신
      </button>
    </div>
  )
}

export default App
