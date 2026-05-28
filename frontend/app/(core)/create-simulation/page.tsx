"use client";

import { useEffect } from 'react';
import { useForm } from "react-hook-form";
import { useRouter } from 'next/navigation';
import { Button, Typography, TextField } from '@mui/material';
import FormErrorBox from '../../components/FormErrorBox';

type Inputs = {
    name: string, 
    numberOfAgent: number,
    simulationPeriod: number,
};

export default function Page() {
    const { register, handleSubmit, watch, setValue, formState: { errors }, } = useForm<Inputs>({ mode: 'onChange', });
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
                    <TextField id="name" label="Name" variant="outlined"  {...register("name", { required: "Name is required" })} />
                    <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                    <TextField id="N" label="Number of agents" variant="outlined" {...register("numberOfAgent", { required: "Number of agents are required", valueAsNumber: true, validate: (value) => !isNaN(value) || "Number of agents must be a valid number", })} />
                    <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                    <TextField id="T" label="Simulation time" variant="outlined" {...register("simulationPeriod", { required: "Simulation time is required", valueAsNumber: true, validate: (value) => !isNaN(value) || "Simulation time must be a valid number", })} /><br/><br/>

                    {/* Error Area */}
                    <FormErrorBox errors={errors} />

                    <Button onClick={handleCancelUpdate}>Cancel</Button>
                    <Button type="submit" variant="contained">Next</Button>
                </fieldset>
            </form>
        </div>
    )
}