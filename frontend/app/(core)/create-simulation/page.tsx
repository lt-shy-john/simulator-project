"use client";

import { useEffect } from 'react';
import { useForm } from "react-hook-form";
import { useRouter } from 'next/navigation';
import { Button, Typography, TextField } from '@mui/material';

type Inputs = {
    name: string, 
    numberOfAgent: number,
    simulationPeriod: number,
};

export default function Page() {
    const { register, handleSubmit, watch, setValue, formState: { errors }, } = useForm<Inputs>();
    const router = useRouter();

    console.log(watch());

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const savedData = sessionStorage.getItem('data');
            console.log('Obtained previous form data. ');
            console.log(savedData);
            if (savedData) {
                const data = JSON.parse(savedData);
                if (data.name) setValue('name', data.name);
                if (data.numberOfAgent) setValue('numberOfAgent', data.numberOfAgent);
                if (data.simulationPeriod) setValue('simulationPeriod', data.simulationPeriod);
            }
        }
    }, [setValue]);

    const handleCancelUpdate = () => {
        console.log("Cancelling simulation update. Removing session item...");
        sessionStorage.removeItem('data');
        router.push("/simulation");
    };

    const onSubmit = (data: Inputs) => {
        const existing = sessionStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        sessionStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        console.log(sessionStorage);
        router.push('/create-simulation-file');
    };

    return (
        <div id='title'>
            <Typography variant="h3">Create Simulation</Typography>
            <form onSubmit={handleSubmit(onSubmit)}>
                <fieldset>
                    <label htmlFor="Name"><Typography variant="body1">Simulation name</Typography></label>
                    <TextField id="name" label="Name" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("name", { required: "Name is required" })} required aria-required="true"/>
                    <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                    <TextField id="N" name="N" label="Number of agents" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("numberOfAgent", { required: "Number of agents are required" })} required aria-required="true"/>
                    <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                    <TextField id="T" name="T" label="Simulation time" variant="outlined" error={!!errors.name} helperText={errors.name?.message} {...register("simulationPeriod", { required: "Simulation time is required" })} required aria-required="true"/><br/><br/>
                    <Button onClick={handleCancelUpdate}>Cancel</Button>
                    <Button type="submit" variant="contained">Next</Button>
                </fieldset>
            </form>
        </div>
    )
}