"use client";

import { useEffect, useState } from "react";
import '../../ui/global.css'

import { useRouter } from 'next/navigation'
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import { DataGrid, GridGetRowsParams, GridGetRowsResponse, GridRowParams, GridActionsCellItem, GridGetRowsError, GridUpdateRowError } from "@mui/x-data-grid";

interface GridDataSource {
    /**
     * This method is called when the grid needs to fetch rows.
     * @param {GridGetRowsParams} params The parameters required to fetch the rows.
     * @returns {Promise<GridGetRowsResponse>} A promise that resolves to the data of
     * type [GridGetRowsResponse].
     */
    getRows(params: GridGetRowsParams): Promise<GridGetRowsResponse>;
}

const customDataSource: GridDataSource = {
    getRows: async (params: GridGetRowsParams): Promise<GridGetRowsResponse> => {
        const response = await fetch('http://localhost:8000/simulations/');
        const data = await response.json();
        console.log(data.length + ' simulation data fetched. ');

        return {
            rows: data,
            //rowCount: data.length,
        };
    },
}

export interface DeleteConfirmProps {
    open: boolean;
    selectedRecord: string;
    onClose: (value: string) => void;
}

async function deleteSimuData(id) {
    const res = await fetch("http://localhost:8000/simulations/"+id+"/", {
        method: "DELETE",
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    if (!res.ok) {
        console.log("Failed to delete data");
        throw new Error("Failed to delete data");
    }
    console.log('Successfully deleted simulation ' + id + '.');
}

function DeleteConfirmDialog(props: DeleteConfirmProps) {
    const { onClose, selectedRecord, open } = props;

    const handleClose = () => {
        onClose();
    };

    const handleCancelDelete = () => {
        onClose();
    };

    const handleDelete = () => {
        console.log('Deleting simulation' + selectedRecord + '.');
        deleteSimuData(selectedRecord);
        location.reload();
        onClose(selectedRecord);
    };

    return (
        <Dialog onClose={handleClose} open={open}>
            <DialogTitle>Confirm Delete</DialogTitle>
            <DialogContent dividers>
                <Typography variant="body1">Please confirm you are deleting this simulation set. </Typography>
            </DialogContent>
            <DialogActions>
                <Button autoFocus onClick={handleCancelDelete}>
                    Cancel
                </Button>
                <Button onClick={handleDelete}>Confirm</Button>
            </DialogActions>
        </Dialog>
    )
}

export default function Page() {
    const [displayDatagrid, setDisplayDatagrid] = useState(false);
    const [openDeleteDialogue, setOpenDeleteDialogue] = useState(false);
    const [deleteId, setdeleteId] = useState(null);

    const router = useRouter();

    useEffect(() => { setTimeout(() => { setDisplayDatagrid(true); });}, []);


    function handleRunSimulation(data) {
        console.log('Running simulation ' + data.id + '.');
        sessionStorage.setItem('simuData', JSON.stringify(data));
        router.push('/simulation/run/' + data.id);
    }
    function handleViewSimulation(data) {
        console.log('Viewing simulation ' + data.id + '.');
        router.push('/view-simulation/' + data.id);
    }
    function handleViewSimulationSetting(data) {
        console.log('Redirecting to setting page simulation ' + data.id + '.');
        router.push('/update-simulation/basic/' + data.id);
    }

    const handleDeleteSimulation = (data) =>  {
        console.log('Deleting simulation ' + data.id + '.');
        setOpenDeleteDialogue(true);
        setdeleteId(data.id);
    }

    const handleDeleteClose = (value: string) => {
        setOpenDeleteDialogue(false);
    };

    const columns = [
        { field: "name", headerName: "Name", hideable: true, width: 150 },
        { field: "numberOfAgent", headerName: "Number of Agents (N)", hideable: true, width: 150 },
        { field: "simulationPeriod", headerName: "Simulation Time (T)", hideable: true, width: 150 },
        { field: "createDate", headerName: "Creation Date", type: 'date', valueGetter: (value) => new Date(value), hideable: true, width: 150 },
        { field: "status", headerName: "Status", hideable: false, width: 150 },
        {
            field: "action", headerName: "Action", type: 'actions', width: 100,
            getActions: (params: GridRowParams) => [
                <GridActionsCellItem onClick={() => { handleRunSimulation(params.row); }} label="Run" showInMenu />,
                <GridActionsCellItem onClick={() => { handleViewSimulation(params.row); }} label="View" showInMenu />,
                <GridActionsCellItem onClick={() => { handleViewSimulationSetting(params.row); }} label="Settings" showInMenu />,
                <GridActionsCellItem onClick={() => { handleDeleteSimulation(params.row); }} label="Delete" showInMenu />,
            ]
        },
    ];

    const [paginationModel, setPaginationModel] = useState({
        page: 0,
        pageSize: 10,
    });

    return (
        <div className="normal-container">
            <div className="crud-header"><Typography variant="h3">Simulation</Typography></div>
            <div className="crud-header"><Button variant="contained" href='/create-simulation'>Create</Button></div>
            <div style={{ display: 'flex', flexDirection: 'column', height: 400, width: '100%' }}>
                {displayDatagrid && <DataGrid columns={columns} dataSource={customDataSource} pagination onPaginationModelChange={setPaginationModel}
                    initialState={{ columns: { columnVisibilityModel: { numberOfAgent: false, simulationPeriod: false } }, pagination: { paginationModel: paginationModel, rowCount: 0 } }}
                    onDataSourceError={(error) => {
                        if (error instanceof GridGetRowsError) {
                            // `error.params` is of type `GridGetRowsParams`
                            // fetch related logic, e.g set an overlay state
                            console.group('== GridGetRowsError ==');
                            console.error('There is an error when getting simulation data.');
                            console.error(error);
                            console.groupEnd();
                        }
                        if (error instanceof GridUpdateRowError) {
                            // `error.params` is of type `GridUpdateRowParams`
                            // update related logic, e.g set a snackbar state
                            console.group('== GridUpdateRowError ==');
                            console.error('There is an error when updating simulation data.');
                            console.error(error);
                            console.groupEnd();
                        }
                    }}
                    pageSizeOptions={[paginationModel['pageSize'], paginationModel['pageSize'] * 2, paginationModel['pageSize'] * 3]} /> }
                <DeleteConfirmDialog selectedRecord={deleteId} open={openDeleteDialogue} onClose={handleDeleteClose}/>
            </div>
        </div>
    )
}