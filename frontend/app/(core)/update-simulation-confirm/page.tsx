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

async function setSimuData(data: CreateSimulationData) {
    const res = await fetch("http://localhost:8000/simulations/", {
        method: "POST",
        body: JSON.stringify(data),
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    if (!res.ok) {
        console.log("Failed to fetch data");
        throw new Error("Failed to fetch data");
    }
}

export default function Page() {
    const { handleSubmit, watch } = useForm<CreateSimulationData>();
    const [formData, setFormData] = useState<CreateSimulationData>({});
    const router = useRouter();

    console.log(watch());

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const stored = localStorage.getItem('data');
            if (stored) {
                setFormData(JSON.parse(stored));
            }
        }
    }, []);

    const onSubmit = (data: CreateSimulationData) => {
        const existing = localStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        localStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        console.log(localStorage);
        setSimuData({ ...formData, createdBy: { username: "johnyeung" } }); 
        localStorage.removeItem('data');
        console.log("Data submitted.");
        router.push('/simulation');
    };

  return (
    <div id='title'>
      <Typography variant="h3">Create Simulation</Typography>
          <form onSubmit={handleSubmit(onSubmit)}>
              <fieldset>
                  <legend><Typography variant="h4">Confirmation</Typography></legend>
                  <label>Number of agents (N)</label>
                  <p>{formData['numberOfAgent']}</p>
                  <label>Simulation time (T)</label>
                  <p>{formData['simulationPeriod']}</p>
                <Button>Cancel</Button>
                <Button type="submit" variant="contained">Next</Button>
              </fieldset>
          </form>
    </div>
  )
}