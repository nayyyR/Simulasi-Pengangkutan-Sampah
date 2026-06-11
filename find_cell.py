import json, sys
sys.stdout.reconfigure(encoding='utf-8')

NB_PATH = 'Simulasi_Sampah_DKA.ipynb'
with open(NB_PATH, 'r', encoding='utf-8') as f:
    nb = json.load(f)

flask_cell_code = '''## Taruh sini aja kalau bisa
# ============================================================
# FLASK API SERVER — Jalankan simulasi Python & expose ke index.html
# Jalankan cell ini, lalu buka: http://localhost:5000
# index.html akan otomatis punya tombol "▶ Python API"
# ============================================================

# Install kalau belum ada: pip install flask flask-cors
import threading, math, random as _random, copy
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    from flask import Flask, jsonify, request, send_file
    from flask_cors import CORS
    FLASK_OK = True
except ImportError:
    print("Install dulu: pip install flask flask-cors")
    FLASK_OK = False

if FLASK_OK:

    # ── Konstanta (sama persis dengan Cell 1) ──────────────────
    _G_START=360; _G_END=900; _T_START=480; _T_END=1020
    _CAP_G=15; _CAP_T=200; _TPS_MIN=400; _TPS_MAX=500
    _TRASH_MIN=0; _TRASH_MAX=7; _GRID=50; _N_HOUSES=100; _N_TPS=3
    _G_LOAD=2; _T_LOAD=2; _G_TRAV=3; _T_TRAV5=3

    def _euclidean(a, b):
        return math.sqrt((a[0]-b[0])**2+(a[1]-b[1])**2)

    def _gtravel(d): return d * _G_TRAV
    def _ttravel(d): return d * (_T_TRAV5 / 5.0)
    def _gload(kg):  return kg * _G_LOAD
    def _tload(kg):  return (kg / 10.0) * _T_LOAD

    def _hhmm(m):
        h=int(m)//60; mn=int(m)%60
        return f"{h:02d}:{mn:02d}"

    # ── Kelas Data (standalone, tidak bergantung Cell lain) ────
    class _House:
        def __init__(self,id,x,y,trash):
            self.id=id; self.x=x; self.y=y
            self.trash0=trash; self.trash=trash
        @property
        def pos(self): return (self.x,self.y)

    class _TPS:
        def __init__(self,id,x,y,cap):
            self.id=id; self.x=x; self.y=y; self.cap=cap; self.stored=0.0
        @property
        def pos(self): return (self.x,self.y)

    class _Gerobak:
        def __init__(self,id,x,y):
            self.id=id; self.x=x; self.y=y
            self.load=0.0; self.time=_G_START; self.active=True; self.done=False
            self.trips_tps=0; self.trips_truk=0; self.total_dist=0.0
        @property
        def pos(self): return (self.x,self.y)
        def move_to(self,tx,ty):
            d=_euclidean(self.pos,(tx,ty)); t=_gtravel(d)
            self.x=tx; self.y=ty; self.time+=t; self.total_dist+=d
        def collect(self,h,kg):
            h.trash=max(0,h.trash-kg); self.load+=kg; self.time+=_gload(kg)
        def dump_tps(self,tps):
            tps.stored=min(tps.cap,tps.stored+self.load)
            self.time+=_gload(self.load); self.load=0.0; self.trips_tps+=1
        def dump_truk(self,t,kg):
            self.load=max(0,self.load-kg); self.time+=_gload(kg); self.trips_truk+=1
            t.receive(self,kg)

    class _Truk:
        def __init__(self,id,tps):
            self.id=id; self.x=tps.x; self.y=tps.y; self.home_tps=tps
            self.load=0.0; self.time=_T_START; self.active=True; self.done=False
            self.trips_tps=0; self.total_dist=0.0; self.recv_kg=0.0
        @property
        def pos(self): return (self.x,self.y)
        def move_to(self,tx,ty):
            d=_euclidean(self.pos,(tx,ty)); t=_ttravel(d)
            self.x=tx; self.y=ty; self.time+=t; self.total_dist+=d
        def collect(self,h,kg):
            h.trash=max(0,h.trash-kg); self.load+=kg; self.time+=_tload(kg)
        def dump_tps(self,tps):
            tps.stored=min(tps.cap,tps.stored+self.load)
            self.time+=_tload(self.load); self.load=0.0; self.trips_tps+=1
        def receive(self,g,kg):
            self.load+=kg; self.time+=_tload(kg); self.recv_kg+=kg

    # ── Helper functions ───────────────────────────────────────
    def _nearest_tps(pos, tps_list):
        cands=[t for t in tps_list if t.stored<t.cap*0.99]
        if not cands: return tps_list[0]
        return min(cands,key=lambda t:_euclidean(pos,t.pos))

    def _nearest_house(pos,houses):
        cands=[h for h in houses if h.trash>0.05]
        if not cands: return None
        return min(cands,key=lambda h:_euclidean(pos,h.pos))

    def _batch_plan(truk,houses,mx=6):
        plan=[]; cap=_CAP_T-truk.load; cur=truk.pos; vis=set()
        while cap>0.5 and len(plan)<mx:
            cands=[h for h in houses if h.id not in vis and h.trash>0.05]
            if not cands: break
            best=min(cands,key=lambda h:_euclidean(cur,h.pos))
            take=min(best.trash,cap); plan.append((best,take))
            cap-=take; cur=(best.x,best.y); vis.add(best.id)
        return plan

    # ── Fungsi Simulasi Utama ──────────────────────────────────
    def run_simulation(seed=None):
        if seed is None:
            import time as _time
            seed = int(_time.time()) % 99999 + 1
        rng = _random.Random(seed)

        # Generate peta
        pos_used = set()
        def uid():
            while True:
                x=round(rng.uniform(1,_GRID-1),1); y=round(rng.uniform(1,_GRID-1),1)
                k=f"{x},{y}"
                if k not in pos_used:
                    pos_used.add(k); return x,y

        houses = []
        for i in range(_N_HOUSES):
            x,y=uid(); tr=round(rng.uniform(_TRASH_MIN,_TRASH_MAX),2)
            houses.append(_House(i+1,x,y,tr))

        tps_list = []
        for i in range(_N_TPS):
            x,y=uid(); cap=round(rng.uniform(_TPS_MIN,_TPS_MAX),1)
            tps_list.append(_TPS(i+1,x,y,cap))

        NG=rng.randint(5,7); NT=rng.randint(2,4)

        gerobaks=[]
        for i in range(NG):
            x,y=uid(); gerobaks.append(_Gerobak(i+1,x,y))

        truks=[]
        for i in range(NT):
            tp=tps_list[i%_N_TPS]; truks.append(_Truk(i+1,tp))

        # Simpan snapshot awal
        snap_gerobak = {g.id:(g.x,g.y) for g in gerobaks}

        # Rekam frames tiap 5 menit simulasi
        FRAME_INTERVAL = 5
        frames = []
        last_frame_time = _G_START

        def snapshot(t):
            return {
                "time": round(t,1),
                "time_str": _hhmm(t),
                "gerobak": [{"id":g.id,"x":round(g.x,2),"y":round(g.y,2),
                              "load":round(g.load,2),"active":g.active} for g in gerobaks],
                "truk":    [{"id":t2.id,"x":round(t2.x,2),"y":round(t2.y,2),
                              "load":round(t2.load,2),"active":t2.active} for t2 in truks],
                "houses":  [{"id":h.id,"trash":round(h.trash,2)} for h in houses],
                "tps":     [{"id":tp.id,"stored":round(tp.stored,1)} for tp in tps_list]
            }

        frames.append(snapshot(_G_START))

        # Loop simulasi concurrent
        gerobak_done=[False]*NG; truk_done=[False]*NT; iteration=0

        while not(all(gerobak_done) and all(truk_done)):
            iteration+=1
            if iteration>500_000: break

            active_g=[(i,g) for i,g in enumerate(gerobaks) if not gerobak_done[i]]
            active_t=[(i,t) for i,t in enumerate(truks) if not truk_done[i]]
            cands=[("g",i,a) for i,a in active_g]+[("t",i,a) for i,a in active_t]
            if not cands: break

            ag_type,idx,ag=min(cands,key=lambda x:x[2].time)

            # Rekam frame tiap FRAME_INTERVAL menit
            cur_t = ag.time
            if cur_t - last_frame_time >= FRAME_INTERVAL:
                frames.append(snapshot(cur_t))
                last_frame_time = cur_t

            if ag_type=="g":
                g=ag
                if g.time>=_G_END:
                    gerobak_done[idx]=True; continue

                if g.load>=_CAP_G*0.9:
                    best_t=None; best_d=float('inf')
                    for t in truks:
                        if t.time>=_T_END: continue
                        d=_euclidean(g.pos,t.pos)
                        if d<best_d and (_CAP_T-t.load)>=5 and d<12:
                            best_d=d; best_t=t
                    if best_t:
                        nt=_nearest_tps(g.pos,tps_list)
                        dt=_euclidean(g.pos,nt.pos) if nt else float('inf')
                        if best_d<dt*0.75:
                            g.move_to(best_t.x,best_t.y)
                            if g.time>=_G_END: gerobak_done[idx]=True; continue
                            kg=min(g.load,_CAP_T-best_t.load)
                            g.dump_truk(best_t,kg); continue
                    tps=_nearest_tps(g.pos,tps_list)
                    if not tps: gerobak_done[idx]=True; continue
                    g.move_to(tps.x,tps.y)
                    if g.time>=_G_END: gerobak_done[idx]=True; continue
                    g.dump_tps(tps); continue

                h=_nearest_house(g.pos,houses)
                if not h:
                    if g.load>0.01:
                        tps=_nearest_tps(g.pos,tps_list)
                        if tps: g.move_to(tps.x,tps.y); g.dump_tps(tps) if g.time<_G_END else None
                    gerobak_done[idx]=True; continue

                g.move_to(h.x,h.y)
                if g.time>=_G_END: gerobak_done[idx]=True; continue
                take=min(h.trash,_CAP_G-g.load)
                if take>0.01: g.collect(h,take)

                for t in truks:
                    if t.time>=_T_END: continue
                    d=_euclidean(g.pos,t.pos)
                    if d<5.0 and g.load>=3.0 and (_CAP_T-t.load)>=3.0:
                        nt=_nearest_tps(g.pos,tps_list)
                        dt=_euclidean(g.pos,nt.pos) if nt else float('inf')
                        if d<dt*0.75:
                            kg=min(g.load,_CAP_T-t.load)
                            g.dump_truk(t,kg); break

            else:
                t=ag
                if t.time<_T_START: t.time=_T_START; continue
                if t.time>=_T_END: truk_done[idx]=True; continue

                if t.load>=_CAP_T*0.9:
                    tps=_nearest_tps(t.pos,tps_list)
                    if not tps: truk_done[idx]=True; continue
                    t.move_to(tps.x,tps.y)
                    if t.time>=_T_END: truk_done[idx]=True; continue
                    t.dump_tps(tps); continue

                plan=_batch_plan(t,houses,6)
                if not plan:
                    if t.load>0.01:
                        tps=_nearest_tps(t.pos,tps_list)
                        if tps: t.move_to(tps.x,tps.y); t.dump_tps(tps) if t.time<_T_END else None
                    truk_done[idx]=True; continue

                for (h,kg) in plan:
                    if t.time>=_T_END: truk_done[idx]=True; break
                    if h.trash<0.01: continue
                    t.move_to(h.x,h.y)
                    if t.time>=_T_END: truk_done[idx]=True; break
                    actual=min(h.trash,_CAP_T-t.load)
                    if actual>0.01: t.collect(h,actual)
                    if t.load>=_CAP_T*0.95: break

        # Frame terakhir
        frames.append(snapshot(max(g.time for g in gerobaks+truks)))

        # Hitung stats
        total_awal = sum(h.trash0 for h in houses)
        di_tps     = sum(tp.stored for tp in tps_list)
        rumah_bersih = sum(1 for h in houses if h.trash<0.05)

        return {
            "seed": seed,
            "num_gerobak": NG,
            "num_truk": NT,
            "iterations": iteration,
            "houses": [{"id":h.id,"x":h.x,"y":h.y,"trash_initial":h.trash0} for h in houses],
            "tps_list": [{"id":tp.id,"x":tp.x,"y":tp.y,"capacity":tp.cap} for tp in tps_list],
            "gerobak_agents": [{"id":g.id,"sx":snap_gerobak[g.id][0],"sy":snap_gerobak[g.id][1]} for g in gerobaks],
            "truk_agents": [{"id":t.id,"sx":t.home_tps.x,"sy":t.home_tps.y,"home_tps":t.home_tps.id} for t in truks],
            "frames": frames,
            "stats": {
                "total_awal_kg": round(total_awal,2),
                "di_tps_kg":     round(di_tps,2),
                "rumah_bersih":  rumah_bersih,
                "efisiensi_pct": round(di_tps/total_awal*100,1) if total_awal>0 else 0
            }
        }

    # ── Flask App ──────────────────────────────────────────────
    flask_app = Flask(__name__)
    CORS(flask_app)

    @flask_app.route('/api/simulate', methods=['POST','GET'])
    def api_simulate():
        seed = None
        if request.method=='POST' and request.is_json:
            seed = request.json.get('seed')
        result = run_simulation(seed)
        return jsonify(result)

    @flask_app.route('/')
    def serve_index():
        return send_file('index.html')

    # Jalankan di thread background (tidak blocking notebook)
    def _start_server():
        flask_app.run(port=5000, debug=False, use_reloader=False)

    if not any(t.name=='flask-sim' for t in threading.enumerate()):
        t = threading.Thread(target=_start_server, name='flask-sim', daemon=True)
        t.start()
        print("=" * 55)
        print("  Flask API aktif di: http://localhost:5000")
        print("  Endpoint: POST/GET http://localhost:5000/api/simulate")
        print("  Buka index.html → klik tombol  Python API")
        print("=" * 55)
    else:
        print("Server sudah berjalan di http://localhost:5000")
'''

# Tulis ke Cell 18
nb['cells'][18]['source'] = flask_cell_code
nb['cells'][18]['outputs'] = []
nb['cells'][18]['execution_count'] = None

with open(NB_PATH, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print('Cell 18 berhasil diisi dengan Flask API!')
