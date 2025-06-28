from flask import Flask, request, jsonify, send_file, render_template
import sqlite3, os, io, pandas as pd, matplotlib.pyplot as plt
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

DB = 'sensor_data.db'
ARCHIVE_DIR = 'archive'
IMAGE_DIR = 'static/images'
TARGET_EC = 500    # ppm
WAIT_MIN  = 30     # default mins between corrections
last_correction = datetime.min

app = Flask(__name__, static_folder='static')

# ---------- helpers ----------

def get_db():
    conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("""CREATE TABLE IF NOT EXISTS sensor_data(
                  id INTEGER PRIMARY KEY,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  water_temp REAL,
                  tds_ppm REAL)""")
    return conn

# ---------- routes ----------

@app.post('/sensor_data')
def sensor_data():
    data = request.get_json(force=True)
    conn = get_db()
    conn.execute("INSERT INTO sensor_data(water_temp,tds_ppm) VALUES(?,?)",
                 (data['water_temp'], data['tds']))
    conn.commit(); conn.close()
    return {'status':'ok'}

@app.get('/next_pump_runtime')
def next_pump():
    global last_correction
    now = datetime.now()
    if (now - last_correction).total_seconds() < WAIT_MIN*60:
        return '0'
    conn = get_db(); cur = conn.execute("SELECT tds_ppm FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cur.fetchone(); conn.close()
    current = row[0] if row else TARGET_EC
    err = TARGET_EC - current
    seconds = max(0, min(10, int(err/50)))  # crude proportional control
    if seconds>0: last_correction = now
    return str(seconds)

@app.get('/download_data')
def download():
    conn = get_db(); df = pd.read_sql_query("SELECT * FROM sensor_data", conn); conn.close()
    csv = 'sensor_data.csv'; df.to_csv(csv, index=False)
    return send_file(csv, as_attachment=True)

@app.get('/graph24h')
def graph24h():
    conn = get_db()
    since = datetime.now()-timedelta(hours=24)
    df = pd.read_sql_query("SELECT * FROM sensor_data WHERE timestamp>=?", conn, params=(since,))
    conn.close()
    if df.empty:
        return {'error':'no data'}
    fig, ax = plt.subplots()
    ax.plot(pd.to_datetime(df['timestamp']), df['water_temp'], label='Water °C')
    ax.plot(pd.to_datetime(df['timestamp']), df['tds_ppm'], label='TDS ppm')
    ax.legend(); ax.set_xlabel('time'); ax.set_title('Last 24 h')
    os.makedirs(IMAGE_DIR, exist_ok=True)
    path = os.path.join(IMAGE_DIR,'last24h.png'); fig.savefig(path); plt.close(fig)
    return send_file(path)

@app.post('/api/settings')
def set_settings():
    global TARGET_EC, WAIT_MIN
    js = request.get_json(force=True)
    TARGET_EC = float(js.get('target_ec', TARGET_EC))
    WAIT_MIN  = int(js.get('wait_min',  WAIT_MIN))
    return {'target_ec':TARGET_EC,'wait_min':WAIT_MIN}

# ---------- archiver ----------

def daily_archive():
    conn = get_db(); df = pd.read_sql_query("SELECT * FROM sensor_data", conn); conn.close()
    if df.empty: return
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    df.to_csv(os.path.join(ARCHIVE_DIR, datetime.now().strftime('%Y-%m-%d')+'.csv'), index=False)

sched = BackgroundScheduler(); sched.add_job(daily_archive,'cron',hour=23,minute=59); sched.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
