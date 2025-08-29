"use client";

import { use, useEffect, useState } from 'react';
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

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const router = useRouter();
    const { id } = use(params);

  return (
      <div id='title'>
          <Typography variant="h3">Simulation</Typography>
          <Typography variant="h6">ID</Typography>
          <Typography variant="body1">{id}</Typography>
          <Typography variant="h6">Number of agents (N)</Typography>
          <Typography variant="body1">{/*<p>{formData['numberOfAgent']}</p>*/}</Typography>
          <Typography variant="h6">Simulation time (T)</Typography>
          <Typography variant="body1">{/*<p>{formData['simulationPeriod']}</p>*/}</Typography>
    </div>
  )
}