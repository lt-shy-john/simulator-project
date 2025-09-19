"use client";

import { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { useRouter, useParams } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

type UpdateSimulationData = {
    numberOfAgent: number,
    simulationPeriod: number,
    createdBy: {
        username: string
    }
}

async function updateSimuData(id: string, data: UpdateSimulationData) {
    const res = await fetch("http://localhost:8000/simulations/"+id+"/", {
        method: "PATCH",
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

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const { handleSubmit, watch } = useForm<UpdateSimulationData>();
    const [formData, setFormData] = useState<UpdateSimulationData>({});
    const router = useRouter();
    const { id } = useParams <{ id: string }>();

    console.log(watch());

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const stored = localStorage.getItem('data');
            if (stored) {
                setFormData(JSON.parse(stored));
            }
        }
    }, []);

    const onSubmit = (data: UpdateSimulationData) => {
        const existing = localStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        localStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        console.log(localStorage);
        updateSimuData(id, { ...formData, createdBy: { username: "johnyeung" } }); 
        localStorage.removeItem('data');
        console.log("Data submitted.");
        router.push('/simulation');
    };

  return (
    <div id='title'>
      <Typography variant="h3">Update Simulation</Typography>
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