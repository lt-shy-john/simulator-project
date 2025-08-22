"use client";

import { useEffect, useState } from "react";
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import CardButton from '../components/CardButton'

export default function Page() {
  return (
    <div id='title'>
      <div id='heading'>
        <Typography variant="h1">Agent Based Simulator</Typography>
        <p className="content">Easy-to-use simulator, assisting on complex decision making. </p>
        <Button sx={{margin:2}} variant="contained" href='/console'>Try Out</Button>
      </div>
      <div id="use-case">
        <Typography variant="h2">Use Case</Typography>
      </div>
      <div id="get-started">
        <Typography variant="h2">Getting Started</Typography>
        <CardButton header="Tutorial" content="Get started with the step-by-step tutorials. " wip="true"/>
        <CardButton header="Docs" content="Click here for documentations and API guides. " link="/docs"/>
      </div>
    </div>
  )
}