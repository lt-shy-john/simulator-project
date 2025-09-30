"use client";

import { useEffect, useState } from "react";
import { useRouter } from 'next/navigation';
import { Button, Typography } from "@mui/material";

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const [log, setLog] = useState([]);
    const [showLog, setShowLog] = useState(false);

    const coreURL = 'ws://localhost:8001/ws/simulation/';
    const ws = new WebSocket(coreURL);

    const router = useRouter();

    ws.onmessage = (event) => {
        console.log(event.data);
        setLog((p) => [...p, event.data]);
    };
    useEffect(() => {
        const simuData = JSON.parse(sessionStorage.getItem('simuData'));
        ws.onopen = (event) => {
            console.log("Connection opened");
            console.log("simuData: " + simuData.numberOfAgent);
            setShowLog(true);
            ws.send(JSON.stringify({ "pk": 1, "action": "run", "request_id": 1, "N": simuData.numberOfAgent, "T": simuData.simulationPeriod }));
        };
  }, []);

  return (
    <div className="normal-container">
      <div className="crud-header">
              <Typography variant="h3">Run</Typography>
      </div>      
          {showLog && <div id="console">
              {log.map((line, index) => <div key={index} id="console-line"><p>{line}</p></div>)}
          </div> }
      <div>
        <Button variant="contained" onClick={() => router.push('/simulation')}>
          Back
        </Button>
      </div>
    </div>
  )
}