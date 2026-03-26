import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' or 'admin'
  const [status, setStatus] = useState({ status: 'offline', database: 'unknown' });
  const [patrolList, setPatrolList] = useState([]);
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(false);

  // 입력을 위한 폼 상태
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

      const patrolRes = await fetch('/api/patrol/list');
      if (patrolRes.ok) {
        const patrolData = await patrolRes.json();
        if (Array.isArray(patrolData)) setPatrolList(patrolData);
      }

      const productRes = await fetch('/api/products');
      if (productRes.ok) {
        const productData = await productRes.json();
        if (Array.isArray(productData)) setProducts(productData);
      }

      const inventoryRes = await fetch('/api/inventory');
      if (inventoryRes.ok) {
        const inventoryData = await inventoryRes.json();
        if (Array.isArray(inventoryData)) setInventory(inventoryData);
      }
    } catch (error) {
      console.error("데이터 로딩 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGilbotData();
    const timer = setInterval(fetchGilbotData, 10000);
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
      <nav className="sidebar">
        <div className="logo">🤖 Gilbot</div>
        <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>📈 대시보드</button>
        <button className={view === 'admin' ? 'active' : ''} onClick={() => setView('admin')}>⚙️ DB 관리</button>
        <div className="status-indicator">
          <span className={`dot ${status.status === 'running' ? 'online' : 'offline'}`}></span>
          {status.status.toUpperCase()}
        </div>
      </nav>

      <main className="content">
        {view === 'dashboard' ? (
          <div className="dashboard-view">
            <header>
              <h1>대장 상황실</h1>
              <p>실시간 패트롤 로그 및 시스템 상태</p>
            </header>

            <section className="status-cards">
              <div className="card">
                <h3>서버 상태</h3>
                <p className={status.status === 'running' ? 'online-text' : 'offline-text'}>{status.status.toUpperCase()}</p>
              </div>
              <div className="card">
                <h3>DB 연결</h3>
                <p className={status.database === 'connected' ? 'online-text' : 'offline-text'}>{status.database.toUpperCase()}</p>
              </div>
              <div className="card">
                <h3>등록 상품 수</h3>
                <p>{products.length} 개</p>
              </div>
            </section>

            <section className="patrol-log">
              <h2>📋 최근 순찰 기록</h2>
              <table>
                <thead>
                  <tr>
                    <th>시간</th>
                    <th>상태</th>
                    <th>웨이포인트</th>
                    <th>슬롯(신규/이동)</th>
                  </tr>
                </thead>
                <tbody>
                  {patrolList.map(log => (
                    <tr key={log.patrol_id}>
                      <td>{new Date(log.start_time).toLocaleString()}</td>
                      <td><span className={`tag ${log.status}`}>{log.status}</span></td>
                      <td>{log.completed_waypoints}/{log.total_waypoints}</td>
                      <td>{log.new_slots}/{log.moved_slots}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        ) : (
          <div className="admin-view">
            <header>
              <h1>데이터 통제실</h1>
              <p>상품 마스터 관리 및 DB 운영</p>
            </header>

            <section className="admin-grid">
              <div className="admin-card">
                <h2>📦 새 상품 등록</h2>
                <form onSubmit={handleAddProduct} className="admin-form">
                  <input type="text" placeholder="상품명" value={newProduct.product_name} onChange={e => setNewProduct({...newProduct, product_name: e.target.value})} required />
                  <input type="text" placeholder="바코드" value={newProduct.barcode} onChange={e => setNewProduct({...newProduct, barcode: e.target.value})} required />
                  <input type="number" placeholder="표준 수량" value={newProduct.standard_qty} onChange={e => setNewProduct({...newProduct, standard_qty: parseInt(e.target.value)})} required />
                  <input type="text" placeholder="카테고리" value={newProduct.category} onChange={e => setNewProduct({...newProduct, category: e.target.value})} />
                  <button type="submit" className="add-btn">등록하기</button>
                </form>
              </div>

              <div className="admin-card">
                <h2>🍬 등록 상품 목록</h2>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>이름</th>
                        <th>바코드</th>
                        <th>표준 수량</th>
                      </tr>
                    </thead>
                    <tbody>
                      {products.map(p => (
                        <tr key={p.product_id}>
                          <td>{p.product_id}</td>
                          <td>{p.product_name}</td>
                          <td>{p.barcode}</td>
                          <td>{p.standard_qty || 0} 개</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="admin-card full-width">
                <h2>📦 실시간 동적 인벤토리 현황 (Slot Tracking)</h2>
                <p className="sub-text">바코드 및 오도메트리 좌표 기반 실시간 위치 추적</p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Slot ID</th>
                        <th>바코드</th>
                        <th>상품명</th>
                        <th>Odom X</th>
                        <th>Odom Y</th>
                        <th>상태</th>
                        <th>최종 업데이트</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inventory.map(item => (
                        <tr key={item.slot_id}>
                          <td>{item.slot_id}</td>
                          <td><code>{item.barcode}</code></td>
                          <td>{item.product_name || '미등록 상품'}</td>
                          <td>{item.odom_x?.toFixed(2) || '0.00'}</td>
                          <td>{item.odom_y?.toFixed(2) || '0.00'}</td>
                          <td><span className={`tag ${item.status}`}>{item.status}</span></td>
                          <td>{new Date(item.last_updated).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="admin-card full-width">
                <h2>🚨 순찰 기록 위험 관리 (삭제)</h2>
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>시간</th>
                      <th>상태</th>
                      <th>액션</th>
                    </tr>
                  </thead>
                  <tbody>
                    {patrolList.map(log => (
                      <tr key={log.patrol_id}>
                        <td>{log.patrol_id}</td>
                        <td>{new Date(log.start_time).toLocaleString()}</td>
                        <td>{log.status}</td>
                        <td><button className="del-btn" onClick={() => handleDeletePatrol(log.patrol_id)}>삭제</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
