import asyncio, json, base64, subprocess, sys, time, urllib.request, os, shutil, tempfile
import websockets
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL=sys.argv[1]; OUT=sys.argv[2]; N=int(sys.argv[3]); FPS=30; W,H=1280,720
DSF=float(sys.argv[4]) if len(sys.argv)>4 else 1.5
ONLY=[int(x) for x in sys.argv[5].split(",")] if len(sys.argv)>5 else None
PORT=9337
async def main():
    prof=tempfile.mkdtemp(prefix="hhchrome")
    proc=subprocess.Popen([CHROME,"--headless=new",f"--remote-debugging-port={PORT}",f"--user-data-dir={prof}",f"--window-size={W},{H}","--force-device-scale-factor=1","--hide-scrollbars","--mute-audio","--no-first-run","--enable-gpu","--ignore-gpu-blocklist","--use-angle=metal","about:blank"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: tabs=json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")); break
            except Exception: time.sleep(0.2)
        ws_url=[t for t in tabs if t["type"]=="page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url,max_size=None) as ws:
            mid=0; events=[]
            async def call(method,params=None,timeout=60):
                nonlocal mid; mid+=1; my=mid
                await ws.send(json.dumps({"id":my,"method":method,"params":params or {}}))
                while True:
                    m=json.loads(await asyncio.wait_for(ws.recv(),timeout))
                    if m.get("id")==my:
                        if "error" in m: raise RuntimeError(f"{method}: {m['error']}")
                        return m.get("result",{})
                    events.append(m)
            async def wait_event(name,timeout=60):
                for i,e in enumerate(events):
                    if e.get("method")==name: events.pop(i); return e
                while True:
                    m=json.loads(await asyncio.wait_for(ws.recv(),timeout))
                    if m.get("method")==name: return m
                    events.append(m)
            await call("Page.enable"); await call("Runtime.enable")
            await call("Emulation.setDeviceMetricsOverride",{"width":W,"height":H,"deviceScaleFactor":DSF,"mobile":False})
            await call("Page.navigate",{"url":URL}); await wait_event("Page.loadEventFired")
            await call("Runtime.evaluate",{"expression":"document.fonts.ready.then(()=>1)","awaitPromise":True})
            await asyncio.sleep(2.0)
            r=await call("Runtime.evaluate",{"expression":"(()=>{const c=document.getElementById('c');const gl=c.getContext('webgl2')||c.getContext('webgl');return [c.width,c.height,!!gl,document.getElementById('num').textContent].join('|')})()","returnByValue":True})
            print("page:",r["result"]["value"],flush=True)
            # freeze time, restart the timeline, then step frame by frame
            await call("Emulation.setVirtualTimePolicy",{"policy":"pause"})
            await call("Runtime.evaluate",{"expression":"dispatchEvent(new KeyboardEvent('keydown',{key:'r'}))"})
            os.makedirs(OUT,exist_ok=True)
            t0=time.time()
            for i in range(N):
                await call("Runtime.evaluate",{"expression":f"window.__recT={i*1000.0/FPS}"})
                await call("Emulation.setVirtualTimePolicy",{"policy":"advance","budget":1000.0/FPS})
                await wait_event("Emulation.virtualTimeBudgetExpired")
                if ONLY is not None and i not in ONLY: continue
                shot=await call("Page.captureScreenshot",{"format":"png"},timeout=60)
                open(f"{OUT}/f{i:04d}.png","wb").write(base64.b64decode(shot["data"]))
                if i%60==0: print("frame",i,round(time.time()-t0,1),"s",flush=True)
    finally:
        proc.terminate(); shutil.rmtree(prof,ignore_errors=True)
asyncio.run(main())
