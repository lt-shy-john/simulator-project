"use client";

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Typography } from '@mui/material';

type SimulationStatus = "CREATED" | "IN_PROGRESS" | "DONE";

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const router = useRouter();

    const [log, setLog] = useState<string[]>([]);
    const [showLog, setShowLog] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);

    const API_BASE = "http://localhost:8000";
    const WS_URL = "ws://localhost:8001/ws/simulation/";

    const updateStatus = async (id: number, status: SimulationStatus) => {
        await fetch(`${API_BASE}/simulation-runs/${id}/update-status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status }),
        });
    };

    const connectWebSocket = (simId: number) => {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;
        const simuData = JSON.parse(sessionStorage.getItem('simuData'));

        ws.onopen = () => {
            console.log("WebSocket connected");
            console.log("simuData: " + simuData.numberOfAgent);
            setShowLog(true);

            ws.send(
                JSON.stringify({
                    pk: simId,
                    action: "run",
                    request_id: simId,
                    N: simuData.numberOfAgent,
                    T: simuData.simulationPeriod,
                })
            );
        };

        ws.onmessage = (event) => {
            setLog((prev) => [...prev, event.data]);
        };

        ws.onclose = async (event) => {
            console.log("WebSocket closed", event.code);

            // Exit code 0 -> success
            if (event.code === 1000 && simId) {
                await updateStatus(simId, "DONE");
            }
        };

        ws.onerror = (err) => {
            console.error("WebSocket error", err);
        };
    };

    useEffect(() => {
        const startSimulation = async () => {
            const { id } = await params; 

            if (!id) {
                throw new Error("Missing simulation ID from route");
            }

            const payload = {
                simulation_id: Number(id),
                createdBy: {
                    username: "johnyeung",
                },
            };

            console.log("POST payload:", payload);

            const res = await fetch(`${API_BASE}/simulation-runs/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (res.status === 201) {
                const data = await res.json();
                await updateStatus(data.id, "CREATED");
                await updateStatus(data.id, "IN_PROGRESS");
                connectWebSocket(data.id, payload);
            } else if (res.status === 409) {
                const data = await res.json();
                connectWebSocket(data.id, payload);
            } else {
                console.error("Unexpected response:", res.status);
            }
        };

        startSimulation();
    }, []);

    return (
        <div className="normal-container">
            <div className="crud-header">
                <Typography variant="h3">Run</Typography>
            </div>
            {showLog && <div id="console">
                {log.map((line, index) => <div key={index} id="console-line"><p>{line}</p></div>)}
            </div>}
            <div>
                <Button variant="contained" onClick={() => router.push('/simulation')}>
                    Back
                </Button>
            </div>
        </div>
    );
}