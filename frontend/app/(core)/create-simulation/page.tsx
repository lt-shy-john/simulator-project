"use client";

import { useEffect } from 'react';
import { useForm } from "react-hook-form";
import { useRouter } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

type Inputs = {
    name: string, 
    numberOfAgent: number,
    simulationPeriod: number,
};

export default function Page() {
    const { register, handleSubmit, watch, setValue } = useForm<Inputs>();
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
        router.push('/create-simulation-confirm');
    };

    return (
        <div id='title'>
            <Typography variant="h3">Create Simulation</Typography>
            <form onSubmit={handleSubmit(onSubmit)}>
                <fieldset>
                    <label htmlFor="Name"><Typography variant="body1">Simulation name</Typography></label>
                    <input type="text" id="Name" name="Name"  {...register("name")} required aria-required="true" /><br />
                    <label htmlFor="N"><Typography variant="body1">Number of agents (N)</Typography></label>
                    <input type="text" id="N" name="N"  {...register("numberOfAgent")} required aria-required="true" /><br />
                    <label htmlFor="T"><Typography variant="body1">Simulation time (T)</Typography></label>
                    <input type="text" id="T" name="T"  {...register("simulationPeriod")} required aria-required="true" /><br /><br />
                    <Button onClick={handleCancelUpdate}>Cancel</Button>
                    <Button type="submit" variant="contained">Next</Button>
                </fieldset>
            </form>
        </div>
    )
}