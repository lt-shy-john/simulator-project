"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Typography } from "@mui/material";

type SimulationStatus = "CREATED" | "IN_PROGRESS" | "DONE" | "ERROR";

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const [log, setLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const startedRef = useRef(false);
  const finishedRef = useRef(false);
  const runIdRef = useRef<number | null>(null);

  const API_BASE = "http://localhost:8000";
  const WS_URL = "ws://localhost:8001/ws/simulation/";

  const updateStatus = async (status: SimulationStatus) => {
    const runId = runIdRef.current;
    if (!Number.isInteger(runId)) return;
    console.log('updateStatus: Updating simulation record '+ runId +' to status '+ status +'.');

    await fetch(`${API_BASE}/simulation-runs/${runId}/update-status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
  };

  const connectWebSocket = (runId: number) => {
    console.group('=== Simulation ===');
    runIdRef.current = runId;
    console.log('Started connecting to '+WS_URL+'.');
    console.log('Run ID: '+runIdRef.current+'.')

    if (wsRef.current) {
        console.log('An existing connection established. Closing connection...');
        wsRef.current.close();
        console.log('Connection closed.');
    }

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;
    console.log('Websocket connection created on '+WS_URL+'.');

    const simuData = JSON.parse(sessionStorage.getItem("simuData") || "{}");
    console.log('Obtained simuData items: '+simuData);

    ws.onopen = async () => {
      setShowLog(true);
      await updateStatus("IN_PROGRESS");

      ws.send(
        JSON.stringify({
          pk: runId,
          action: "run",
          request_id: runId,
          N: simuData.numberOfAgent,
          T: simuData.simulationPeriod,
        })
      );
    };
    console.log('Triggered simulation action to '+WS_URL+'.');

    ws.onmessage = async (event) => {
      const message = event.data as string;

      setLog((prev) => [...prev, message]);

      if (
        !finishedRef.current &&
        message.includes("Process finished. ")
      ) {
        finishedRef.current = true;
        console.log('Detected simulation finished, updating status.');
        await updateStatus("DONE");
      }
    };

    ws.onclose = async (event) => {
      console.log('Closing websocket connection...');
      if (!finishedRef.current) {
        await updateStatus("ERROR");
      }
    };

    ws.onerror = async () => {
      await updateStatus("ERROR");
    };
    console.groupEnd();
  };

  useEffect(() => {
    console.group('=== Set up ===');
    if (startedRef.current) return;
    startedRef.current = true;

    const startSimulation = async () => {
      const { id: simulationId } = await params;

      const payload = {
        simulation_id: Number(simulationId),
        createdBy: { username: "johnyeung" },
       };

      const createRun = async () =>
        fetch(`${API_BASE}/simulation-runs/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let res = await createRun();
      let data = await res.json();

      if (res.status === 201) {
        console.log('New simulation run created with ID '+ data.id +'.');
        connectWebSocket(Number(data.id));
        console.log('Finished simulation run with ID'+data.id+'.');
        return;
      }

      if (res.status === 409) {
        const existingRunId = Number(data.id);
        console.log('Detected existing simulation run. Running simulation run '+existingRunId+'.');

        const runRes = await fetch(`${API_BASE}/simulation-runs/${existingRunId}`);
        const runData = await runRes.json();
        console.log('Status of existing simulation run ID: '+runData.status);

        if (runData.status === "CREATED" || runData.status === "IN_PROGRESS") {
          connectWebSocket(existingRunId);
          return;
        }

       if (runData.status === "DONE" || runData.status === "ERROR") {
         res = await createRun();
         data = await res.json();

         if (res.status === 201) {
           connectWebSocket(Number(data.id));
         }
       }
     }
   };

    startSimulation();
    console.groupEnd();

    return () => {
      wsRef.current?.close();
    };
  }, [params]);

  return (
    <div className="normal-container">
      <div className="crud-header">
        <Typography variant="h3">Run Simulation</Typography>
      </div>

      {showLog && (
        <div id="console">
          {log.map((line, index) => (
            <div key={index} id="console-line">
              <p>{line}</p>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <Button variant="contained" onClick={() => router.push("/simulation")}>
          Back
        </Button>
      </div>
    </div>
  );
}
