"use client";

import { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { useRouter } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

type CreateSimulationData = {
    numberOfAgent: number,
    simulationPeriod: number,
    createdBy: {
        username: string
    }
}

async function getSimuData(id: number) {
    const res = await fetch("http://localhost:8000/simulations/" + id);
    if (!res.ok) {
        console.log("Failed to fetch data");
        throw new Error("Failed to fetch data");
    }
}

export default function Page() {
    const router = useRouter();

  return (
    <div id='title'>
          <Typography variant="h3">Simulation</Typography>
          <Typography variant="h4">Confirmation</Typography>
          <p>Number of agents (N)</p>
          <p>{formData['numberOfAgent']}</p>
          <p>Simulation time (T)</p>
          <p>{formData['simulationPeriod']}</p>
    </div>
  )
}