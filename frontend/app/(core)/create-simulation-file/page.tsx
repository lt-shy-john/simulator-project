"use client";

import { useEffect } from 'react';
import { useForm, Controller } from "react-hook-form";
import { useRouter } from 'next/navigation';
import { Button, FormControl, Typography, Select, MenuItem, } from '@mui/material';

type Inputs = {
    name: string, 
    numberOfAgent: number,
    simulationPeriod: number,
    logLevel: number,
};

export default function Page() {
    const { register, control, handleSubmit, watch, setValue } = useForm<Inputs>({defaultValues: {
      logLevel: 'info',
    },}
    );
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
            <Typography variant="h4">File</Typography>
            <Typography variant="body2">Create files exported from simulation</Typography>
            <form onSubmit={handleSubmit(onSubmit)}>
                <fieldset>
                    <FormControl fullWidth margin="normal">
                        <label htmlFor="Name"><Typography variant="body1">Log level</Typography></label>
                        <Controller
                          name="logLevel"
                          control={control}
                          render={({ field }) => (
                            <Select
                              {...field}
                              labelId="log-level-label"
                              label="Log Level"
                            >
                              <MenuItem value="debug">DEBUG</MenuItem>
                              <MenuItem value="info">INFO</MenuItem>
                              <MenuItem value="debug">WARNING</MenuItem>
                              <MenuItem value="error">ERROR</MenuItem>
                            </Select>
                          )}
                        />
                    </FormControl>
                    <Button onClick={handleCancelUpdate}>Cancel</Button>
                    <Button onClick={() => router.back()}>Back</Button>
                    <Button type="submit" variant="contained">Next</Button>
                </fieldset>
            </form>
        </div>
    )
}