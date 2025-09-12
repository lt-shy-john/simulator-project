"use client";

import { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { useRouter, useParams } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

type Inputs = {
    numberOfAgent: number,
    simulationPeriod: number,
};

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const { register, handleSubmit, watch, setValue } = useForm<Inputs>();
    const router = useRouter();
    const { id } = useParams();

    const [loading, setLoading] = useState(true);
    const [simuData, setSimuData] = useState({});

    console.log(watch());

    useEffect(() => {
        fetch("http://localhost:8000/simulations/" + id).then(response => response.json()).then((json) => setSimuData(json));
        setValue("numberOfAgent", simuData.numberOfAgent);
        setValue("simulationPeriod", simuData.simulationPeriod);
        setLoading(false);
    }, []);

    const onSubmit = (data: Inputs) => {
        const existing = localStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        localStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        router.push('/update-simulation-confirm/basic/'+simuData.id);
    };

    return (
        <div id='title'>
            <Typography variant="h3">Edit Simulation</Typography>
            <form onSubmit={handleSubmit(onSubmit)}>
                {loading ? (<Typography variant="body1">Loading...</Typography>) : (
                    <fieldset>
                        <label htmlFor="ID"><Typography variant="body1">Simulation ID</Typography></label>
                        <Typography variant="body1">{simuData.id}</Typography>
                        <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                        <input type="text" id="N" name="N" {...register("numberOfAgent")} /><br />
                        <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                        <input type="text" id="T" name="T" {...register("simulationPeriod")} /><br /><br />
                        <Button>Cancel</Button>
                        <Button type="submit" variant="contained">Next</Button>
                    </fieldset>)
                }
            </form>
        </div>
    )
}