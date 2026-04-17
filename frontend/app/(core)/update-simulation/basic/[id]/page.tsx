"use client";

import { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { useRouter, useParams } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

type Inputs = {
    name: string,
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
        fetch("http://localhost:8000/simulations/" + id).then(response => response.json()).then((json) => {
            setSimuData(json);
            setValue("name", json.name);
            setValue("numberOfAgent", json.numberOfAgent);
            setValue("simulationPeriod", json.simulationPeriod);
            setLoading(false); }
        );
    }, []);

    const handleCancelUpdate = () => {
        console.log("Cancelling simulation update. Removing session item...");
        sessionStorage.removeItem('data');
        router.push("/simulation");
    };

    const onSubmit = (data: Inputs) => {
        const existing = sessionStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        sessionStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        router.push('/update-simulation-confirm/'+simuData.id);
    };

    return (
        <div id='title'>
            <Typography variant="h3">Edit Simulation</Typography>
            <form onSubmit={handleSubmit(onSubmit)}>
                {loading ? (<Typography variant="body1">Loading...</Typography>) : (
                    <fieldset>
                        <label htmlFor="ID"><Typography variant="body1">Simulation ID</Typography></label>
                        <Typography variant="body1">{simuData.id}</Typography>
                        <label htmlFor="Name"><Typography variant="body1">Simulation name</Typography></label>
                        <input type="text" id="Name" name="Name" {...register("name")} required aria-required="true" /><br />
                        <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                        <input type="text" id="N" name="N" {...register("numberOfAgent")} required aria-required="true" /><br />
                        <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                        <input type="text" id="T" name="T" {...register("simulationPeriod")} required aria-required="true" /><br /><br />
                        <Button onClick={handleCancelUpdate}>Cancel</Button>
                        <Button type="submit" variant="contained">Next</Button>
                    </fieldset>)
                }
            </form>
        </div>
    )
}