"use client";

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const router = useRouter();
    const { id } = useParams();
    console.log('Entered view simulation page for ' + id + ".");

    const [loading, setLoading] = useState(true);
    const [simuData, setSimuData] = useState({});

    useEffect(() => {
        fetch("http://localhost:8000/simulations/" + id).then(response => response.json()).then(json => setSimuData(json));
        setLoading(false);
    }, []);

    return (
        <div id='title'>
            <Typography variant="h3">Simulation</Typography>
            {loading ? (<Typography variant="body1">Loading...</Typography>) : (
                <>
                    <Typography variant="h6">ID</Typography>
                    <Typography variant="body1">{id}</Typography>
                    <Typography variant="h6">Number of agents (N)</Typography>
                    <Typography variant="body1">{simuData.numberOfAgent}</Typography>
                    <Typography variant="h6">Simulation time (T)</Typography>
                    <Typography variant="body1">{simuData.simulationPeriod}</Typography>
                </>
            ) }
    </div>
    )
}