"use client";

import { useEffect, useState } from 'react';
import { useForm } from "react-hook-form";
import { useRouter, useParams } from 'next/navigation';
import { Button, Typography, TextField } from '@mui/material';

type Inputs = {
    name: string,
    numberOfAgent: number,
    simulationPeriod: number,
};

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const { register, handleSubmit, watch, setValue, formState: { errors }, } = useForm<Inputs>();
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
        router.push('/update-simulation-file/'+simuData.id);
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
                        <TextField id="name" label="Name" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("name", { required: "Name is required" })} required aria-required="true"/>
                        <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                        <TextField id="N" name="N" label="Number of agents" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("numberOfAgent", { required: "Number of agents are required" })} required aria-required="true"/>
                        <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                        <TextField id="T" name="T" label="Simulation time" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("simulationPeriod", { required: "Simulation time is required" })} required aria-required="true"/><br/><br/>
                        <Button onClick={handleCancelUpdate}>Cancel</Button>
                        <Button type="submit" variant="contained">Next</Button>
                    </fieldset>)
                }
            </form>
        </div>
    )
}