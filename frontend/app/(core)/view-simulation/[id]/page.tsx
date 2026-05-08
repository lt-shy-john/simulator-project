"use client";

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { Chip } from '@mui/material';
import { grey } from '@mui/material/colors';
import AlarmIcon  from '@mui/icons-material/Alarm';
import { DataGrid, GridGetRowsParams, GridGetRowsResponse, GridRowParams, GridActionsCellItem, GridGetRowsError, GridUpdateRowError } from "@mui/x-data-grid";

import SimuStatus from '../../../components/SimuStatus';

interface GridDataSource {
    /**
     * This method is called when the grid needs to fetch rows.
     * @param {GridGetRowsParams} params The parameters required to fetch the rows.
     * @returns {Promise<GridGetRowsResponse>} A promise that resolves to the data of
     * type [GridGetRowsResponse].
     */
    getRows(params: GridGetRowsParams): Promise<GridGetRowsResponse>;
}

const createCustomDataSource = (id: string): GridDataSource => ({
    getRows: async (params: GridGetRowsParams): Promise<GridGetRowsResponse> => {
        const page = params.paginationModel?.page ?? 0;
        const pageSize = params.paginationModel?.pageSize ?? 10;

        // Backend expects 1-based page index
        const backendPage = page + 1;

        const simRes = await fetch(
            `http://localhost:8000/simulation-runs/by-simulation-id?page=${backendPage}&pagesize=${pageSize}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    simulation_id: id
                }),
             }
        );

        const simData = await simRes.json();

        const simulations = simData.results ?? [];
        const totalCount = simData.count ?? 0;

        console.log(
            `${simulations.length} simulation data fetched. (page ${backendPage})`
        );

        return {
            rows: simulations,
            rowCount: totalCount,
        };
    },
});

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const [displayDatagrid, setDisplayDatagrid] = useState(false);
    useEffect(() => { setTimeout(() => { setDisplayDatagrid(true); }); }, []);

    const router = useRouter();
    const { id } = useParams();
    console.log('Entered view simulation page for ' + id + ".");

    const [loading, setLoading] = useState(true);
    const [simuData, setSimuData] = useState({});

    useEffect(() => {
        fetch("http://localhost:8000/simulations/" + id).then(response => response.json()).then(json => setSimuData(json));
        setLoading(false);
    }, []);

    const columns = [
        { field: "runTime", headerName: "Run Time", hideable: true, width: 300 },
        {
            field: "status", headerName: "Status", hideable: false, width: 150, renderCell: (params) => {
                return <SimuStatus status={params.formattedValue.toLowerCase()} />;
            },
        },
    ];

    const [paginationModel, setPaginationModel] = useState({
        page: 0,
        pageSize: 10,
    });

    const customDataSource = createCustomDataSource(id);

    return (
        <div className="normal-container">
            <div className="crud-header"><Typography variant="h3">Simulation</Typography></div>
            <div className="crud-header"><Button variant="outlined" href='/simulation'>Back</Button></div>
            <div className="crud-header"><Button variant="contained" href='#'>Update</Button></div>
            <div>
                {loading ? (<Typography variant="body1">Loading...</Typography>) : (
                    <>
                        <Typography variant="h6">ID</Typography>
                        <Typography variant="body1">{id}</Typography>
                        <Typography variant="h6">Simulation name</Typography>
                        <Typography variant="body1">{simuData.name}</Typography>
                        <Typography variant="h6">Number of agents (N)</Typography>
                        <Typography variant="body1">{simuData.numberOfAgent}</Typography>
                        <Typography variant="h6">Simulation time (T)</Typography>
                        <Typography variant="body1">{simuData.simulationPeriod}</Typography>
                        <Typography variant="h4">Run Records</Typography>
                        <div style={{ display: 'flex', flexDirection: 'column', height: 400, width: '100%' }}>
                            {displayDatagrid && <DataGrid columns={columns} dataSource={customDataSource} pagination onPaginationModelChange={setPaginationModel} initialState={{
                                pagination: { paginationModel },
                            }}
                                onDataSourceError={(error) => {
                                    if (error instanceof GridGetRowsError) { 
                                        // `error.params` is of type `GridGetRowsParams`
                                        // fetch related logic, e.g set an overlay state 
                                        console.group('== GridGetRowsError ==');
                                        console.error('There is an error when getting simulation data.');
                                        console.error(error);
                                        console.groupEnd();
                                    } if (error instanceof GridUpdateRowError) { 
                                        // `error.params` is of type `GridUpdateRowParams`
                                        // update related logic, e.g set a snackbar state 
                                        console.group('== GridUpdateRowError =='); 
                                        console.error('There is an error when updating simulation data.');
                                        console.error(error);
                                        console.groupEnd();
                                    }
                                }}
                                pageSizeOptions={[paginationModel['pageSize'], paginationModel['pageSize'] * 2, paginationModel['pageSize'] * 3]} />}
                        </div>
                    </>
                )}
            </div>
        </div>
            
       
    )
}