"use client";

import {useCallback, useEffect, useMemo, useState} from "react";

type Device = {id: string; name: string; line_name: string; power_threshold: number; temperature_threshold: number};
type Alarm = {id: string; device_id: string; kind: string; value: number; threshold: number; status: string; assignee?: string; created_at: string};
type Reading = {power_kw: number; temperature_c: number; recorded_at: string};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

async function request(path: string, token: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, {...init, headers: {"Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init?.headers}});
  if (!response.ok) throw new Error((await response.json()).message || "İstek başarısız");
  return response.json();
}

function Sparkline({values}: {values: number[]}) {
  const points = values.length ? values.map((value, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${44 - (value / Math.max(...values, 1)) * 38}`).join(" ") : "0,40 100,40";
  return <svg viewBox="0 0 100 48" preserveAspectRatio="none" className="spark"><polyline points={points}/></svg>;
}

export default function Dashboard() {
  const [token, setToken] = useState("");
  const [devices, setDevices] = useState<Device[]>([]);
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const [readings, setReadings] = useState<Reading[]>([]);
  const [connected, setConnected] = useState(false);
  const [notice, setNotice] = useState("Veri akışı bekleniyor");

  const load = useCallback(async (auth: string) => {
    const [deviceData, alarmData] = await Promise.all([request("/api/v1/devices", auth), request("/api/v1/alarms", auth)]);
    setDevices(deviceData); setAlarms(alarmData);
    if (deviceData[0]) setReadings(await request(`/api/v1/devices/${deviceData[0].id}/measurements?limit=24`, auth));
  }, []);

  useEffect(() => {
    fetch(`${API}/api/v1/auth/login`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({email: "admin@factorypulse.local", password: "factorypulse"})})
      .then(response => response.json()).then(data => {setToken(data.accessToken); return load(data.accessToken)}).catch(() => setNotice("API bağlantısı kurulamadı"));
  }, [load]);

  useEffect(() => {
    if (!token) return;
    const socket = new WebSocket(`${WS}/ws/factories/factory-istanbul?token=${encodeURIComponent(token)}`);
    socket.onopen = () => {setConnected(true); setNotice("Canlı akış bağlı")};
    socket.onclose = () => {setConnected(false); setNotice("Canlı akış yeniden bağlanmayı bekliyor")};
    socket.onmessage = event => {const message = JSON.parse(event.data); setNotice(message.eventType); load(token)};
    const ping = setInterval(() => socket.readyState === WebSocket.OPEN && socket.send("ping"), 15000);
    return () => {clearInterval(ping); socket.close()};
  }, [token, load]);

  const openAlarms = alarms.filter(alarm => alarm.status !== "resolved");
  const latest = readings[0];
  const average = readings.length ? readings.reduce((sum, item) => sum + item.power_kw, 0) / readings.length : 0;
  const chartValues = useMemo(() => [...readings].reverse().map(item => item.power_kw), [readings]);

  async function mutate(path: string, body?: object) {
    await request(path, token, {method: "POST", body: body ? JSON.stringify(body) : undefined});
    await load(token);
  }

  return <main>
    <aside>
      <div className="brand"><span className="logo">FP</span><div><strong>FactoryPulse</strong><small>OPERATIONS</small></div></div>
      <nav><a className="active">Genel Bakış</a><a>Cihazlar</a><a>Alarmlar <b>{openAlarms.length}</b></a><a>Bakım</a><a>Raporlar</a></nav>
      <div className="asideFoot"><span className={connected ? "dot live" : "dot"}/><div><strong>{connected ? "Sistem çevrimiçi" : "Bağlantı bekleniyor"}</strong><small>{notice}</small></div></div>
    </aside>
    <section className="content">
      <header><div><p className="eyebrow">İSTANBUL FABRİKASI · HAT A</p><h1>Operasyon merkezi</h1></div><div className="avatar">MY</div></header>
      <div className="metrics">
        <article><label>ANLIK GÜÇ</label><strong>{latest?.power_kw?.toFixed(1) || "—"}<small> kW</small></strong><Sparkline values={chartValues}/><span>Son 24 ölçüm</span></article>
        <article><label>ORTALAMA GÜÇ</label><strong>{average.toFixed(1)}<small> kW</small></strong><div className="bar"><i style={{width: `${Math.min(average / 30 * 100, 100)}%`}}/></div><span>İzlenen dönem</span></article>
        <article className={openAlarms.length ? "alert" : ""}><label>AÇIK ALARM</label><strong>{openAlarms.length}</strong><div className="alarmGlyph">!</div><span>{openAlarms.length ? "Müdahale gerekiyor" : "Tüm sistemler normal"}</span></article>
        <article><label>AKTİF CİHAZ</label><strong>{devices.length}<small> / {devices.length}</small></strong><div className="nodes">{devices.map(device => <i key={device.id}/>)}</div><span>Hat A izleniyor</span></article>
      </div>
      <div className="grid">
        <article className="panel chartPanel"><div className="panelHead"><div><p className="eyebrow">ENERJİ AKIŞI</p><h2>Canlı tüketim</h2></div><span className="pill">SON 24 ÖLÇÜM</span></div><div className="bigChart"><span className="axis">30<br/>20<br/>10<br/>0</span><Sparkline values={chartValues}/></div></article>
        <article className="panel"><div className="panelHead"><div><p className="eyebrow">FİLO DURUMU</p><h2>Cihazlar</h2></div><span className="pill green">{devices.length} AKTİF</span></div><div className="deviceList">{devices.map(device => <div className="device" key={device.id}><span className="machine">M</span><div><strong>{device.name}</strong><small>{device.line_name} · {device.id}</small></div><em>ÇALIŞIYOR</em></div>)}</div></article>
        <article className="panel alarms"><div className="panelHead"><div><p className="eyebrow">MÜDAHALE KUYRUĞU</p><h2>Alarmlar ve bakım</h2></div></div>{openAlarms.length === 0 ? <div className="empty"><b>✓</b><strong>Açık alarm yok</strong><span>Yeni olaylar burada görünecek.</span></div> : <div className="alarmList">{openAlarms.map(alarm => <div className="alarmRow" key={alarm.id}><span className="severity">YÜKSEK</span><div><strong>{alarm.kind === "power" ? "Güç eşiği aşıldı" : "Sıcaklık eşiği aşıldı"}</strong><small>{alarm.device_id} · {alarm.value.toFixed(1)} / eşik {alarm.threshold}</small></div>{alarm.status === "open" ? <button onClick={() => mutate(`/api/v1/alarms/${alarm.id}/assign`, {technician: "tech@factorypulse.local"})}>Üstlen</button> : <button onClick={() => mutate(`/api/v1/alarms/${alarm.id}/resolve`)}>Çöz</button>}</div>)}</div>}</article>
      </div>
    </section>
  </main>;
}

