"use client";

import { Button } from "@mui/material";
import { useEffect, useState } from "react";
import { useRouter } from 'next/navigation'

export default function Page() {
  const [log, setLog] = useState([]);
  const [showLog, setShowLog] = useState(false);

  const url = 'ws://localhost:8001/ws/simulation/'
  const ws = new WebSocket(url);
  let consoleLog = [];

  const router = useRouter()

  ws.onmessage = (event) => {
    setShowLog(true);
    console.log(event.data);
    setLog((p) => [...p, event.data]);
  };
  useEffect(() => {ws.onopen = (event) => {
      console.log("Connection opened");
      ws.send(JSON.stringify({"pk": 1, "action": "run", "request_id": 1, "N": 21, "T": 20}));
    }
  }, [])

  return (
    <div className="normal-container">
      <div className="crud-header">
        <h1>Run</h1>
      </div>      
      <div id="console">
        {showLog && log.map((line, index) => <div key={index} id="console-line"><p>{line}</p></div>)}
      </div>
      <div>
        <Button variant="contained" onClick={() => router.back()}>
          Back
        </Button>
      </div>
    </div>
  )
}