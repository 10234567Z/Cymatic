"""
Twilio test script — run this standalone to test:
1. Twilio lifts the call
2. Says a greeting via TTS
3. Streams your voice audio to a local WebSocket
4. Prints received audio events in terminal so you can confirm stream is live

Usage:
  uv run uvicorn test_twilio:app --port 8000 --reload
  Then in another terminal: ngrok http 8000
  Set Twilio webhook to: https://<ngrok-url>/test/inbound
"""

import base64
import json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

app = FastAPI()


@app.post("/test/inbound")
async def inbound_call(request: Request):
    form = await request.form()
    caller = form.get("From", "unknown")
    call_sid = form.get("CallSid", "unknown")

    print(f"\n📞 Incoming call from {caller} | CallSid: {call_sid}")

    # BASE_URL must be your ngrok wss:// URL
    # e.g. if ngrok gives https://abc123.ngrok.io → use wss://abc123.ngrok.io
    base_url = request.base_url
    ws_url = str(base_url).replace("http", "ws") + "test/stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Hello! This is Cymatic. Your call is connected to Abhinav.
        I am now streaming your audio. Please say something after the beep.
    </Say>
    
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
    <Say voice="Polly.Joanna">
        Stream has ended. Thank you for testing. Goodbye.
    </Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@app.websocket("/test/stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    print("\n🔴 Media stream CONNECTED")

    audio_chunks_received = 0
    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"▶️  Stream started | StreamSid: {stream_sid}")

            elif event == "media":
                audio_chunks_received += 1
                payload = data["media"]["payload"]
                audio_bytes = base64.b64decode(payload)
                audio_buffer.extend(audio_bytes)
                if audio_chunks_received % 20 == 0:
                    print(f"🎤 Audio chunk #{audio_chunks_received} received | {len(audio_bytes)} bytes")

            elif event == "stop":
                print(f"⏹️  Stream stopped | Total chunks received: {audio_chunks_received}")
                break

    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected | Total chunks received: {audio_chunks_received}")

    finally:
        if audio_buffer:
            raw_path = "recording.raw"
            with open(raw_path, "wb") as f:
                f.write(audio_buffer)
            print(f"\n💾 Saved {len(audio_buffer)} bytes → {raw_path}")
            print("▶️  To play it, run:")
            print(f"   ffmpeg -f mulaw -ar 8000 -ac 1 -i {raw_path} recording.mp3 && open recording.mp3")
