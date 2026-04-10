"use client";

import { useEffect, useState, useRef } from 'react';
import { useForm } from "react-hook-form";
import { useRouter, useParams } from 'next/navigation';
import { Button, ButtonGroup, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Grow from '@mui/material/Grow';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import MenuItem from '@mui/material/MenuItem';
import MenuList from '@mui/material/MenuList';
import Typography from '@mui/material/Typography';

type UpdateSimulationData = {
    name: string,
    numberOfAgent: number,
    simulationPeriod: number,
    createdBy: {
        username: string
    }
}

export interface UpdateConfirmProps {
    open: boolean;
    selectedRecord: string;
    onClose: (value: string) => void;
}

async function updateSimuData(id: string, data: UpdateSimulationData) {
    const res = await fetch("http://localhost:8000/simulations/" + id + "/", {
        method: "PATCH",
        body: JSON.stringify(data),
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    if (!res.ok) {
        console.log("Failed to fetch data");
        throw new Error("Failed to fetch data");
    }
}

function UpdateConfirmDialog(props: UpdateConfirmProps & { onConfirm: () => void }) {
    const { onClose, selectedRecord, open } = props;

    const handleClose = () => {
        onClose();
    };

    const handleCancelUpdate = () => {
        onClose();
    };

    return (
        <Dialog onClose={handleClose} open={open}>
            <DialogTitle>Confirm Update</DialogTitle>
            <DialogContent dividers>
                <Typography variant="body1">Please confirm you are updating this simulation set. </Typography>
            </DialogContent>
            <DialogActions>
                <Button autoFocus onClick={handleCancelUpdate}>
                    Cancel
                </Button>
                <Button onClick={props.onConfirm}>Confirm</Button>
            </DialogActions>
        </Dialog>
    )
}

async function postSimuData(id: string, data: UpdateSimulationData) {
    const res = await fetch("http://localhost:8000/simulations/", {
        method: "POST",
        body: JSON.stringify(data),
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    if (!res.ok) {
        console.log("Failed to fetch data");
        throw new Error("Failed to fetch data");
    }
}

const submitOptions = ['Update existing simulation'];

export default function Page({ params, }: { params: Promise<{ id: string }> }) {
    const { handleSubmit, watch } = useForm<UpdateSimulationData>();
    const [formData, setFormData] = useState<UpdateSimulationData>({});
    const router = useRouter();
    const { id } = useParams<{ id: string }>();

    const [open, setOpen] = useState(false);
    const anchorRef = useRef<HTMLDivElement>(null);
    const [selectedIndex, setSelectedIndex] = useState(1);

    const [openUpdateDialogue, setOpenUpdateDialogue] = useState(false);
    const [updateId, setUpdateId] = useState(null);

    console.log(watch());

    const handleMenuItemClick = (
        event: React.MouseEvent<HTMLLIElement, MouseEvent>,
        index: number,
        id: string
    ) => {
        setSelectedIndex(index);
        setOpen(false);
        handleUpdateSimulation(id);
    };

    const handleSubmitUpdateToggle = () => {
        setOpen((prevOpen) => !prevOpen);
    };

    const handleSubmitUpdateClose = (event: Event) => {
        if (
            anchorRef.current &&
            anchorRef.current.contains(event.target as HTMLElement)
        ) {
            return;
        }

        setOpen(false);
    };

    useEffect(() => {
        if (typeof window !== 'undefined') {
            const stored = sessionStorage.getItem('data');
            if (stored) {
                setFormData(JSON.parse(stored));
            }
        }
    }, []);

    const onSubmit = (data: UpdateSimulationData) => {
        const existing = sessionStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        sessionStorage.setItem('data', JSON.stringify({ ...formData, ...data }));
        console.log(sessionStorage);
        postSimuData(id, { ...formData, createdBy: { username: "johnyeung" } }); 
        sessionStorage.removeItem('data');
        console.log("Data submitted.");
        router.push('/simulation');
    };

    const handleUpdateSimulation = (id) => {
        console.log('Updating simulation ' + id + '.'); setOpenUpdateDialogue(true); setUpdateId(id);
    }

    const handleUpdateClose = (value: string) => { setOpenUpdateDialogue(false); };

    const handleUpdate = (id: string) => {
        if (!id) return;
        console.log('Updating simulation ' + id + '.');
        const existing = sessionStorage.getItem('data');
        const formData = existing ? JSON.parse(existing) : {};
        console.log(existing);
        updateSimuData(id, { ...formData, createdBy: { username: "johnyeung" } });
        sessionStorage.removeItem('data');
        console.log("Data submitted.");
        router.push('/simulation');
    };

  return (
    <div id='title'>
      <Typography variant="h3">Update Simulation</Typography>
          <form onSubmit={handleSubmit(onSubmit)}>
              <fieldset>
                  <legend><Typography variant="h4">Confirmation</Typography></legend>
                  <label>Simulation name</label>
                  <p>{formData['name']}</p>
                  <label>Number of agents (N)</label>
                  <p>{formData['numberOfAgent']}</p>
                  <label>Simulation time (T)</label>
                  <p>{formData['simulationPeriod']}</p>
                  <Button>Cancel</Button>
                  <ButtonGroup
                      variant="contained"
                      ref={anchorRef}
                      aria-label="Button group with a nested menu"
                  >
                      <Button type="submit" variant="contained">Create New Copy</Button>
                      <Button
                          size="small"
                          aria-controls={open ? 'split-button-menu' : undefined}
                          aria-expanded={open ? 'true' : undefined}
                          aria-label="select merge strategy"
                          aria-haspopup="menu"
                          onClick={handleSubmitUpdateToggle}
                      >
                          <ArrowDropDownIcon />
                      </Button>
                  </ButtonGroup>
                  <Popper
                      sx={{ zIndex: 1 }}
                      open={open}
                      anchorEl={anchorRef.current}
                      role={undefined}
                      transition
                      disablePortal
                  >
                      {({ TransitionProps, placement }) => (
                          <Grow
                              {...TransitionProps}
                              style={{
                                  transformOrigin:
                                      placement === 'bottom' ? 'center top' : 'center bottom',
                              }}
                          >
                              <Paper>
                                  <ClickAwayListener onClickAway={handleSubmitUpdateClose}>
                                      <MenuList id="split-button-menu" autoFocusItem>
                                          {submitOptions.map((option, index) => (
                                              <MenuItem
                                                  key={option}
                                                  selected={index === selectedIndex}
                                                  onClick={(event) => handleMenuItemClick(event, index, id)}
                                              >
                                                  {option}
                                              </MenuItem>
                                          ))}
                                      </MenuList>
                                  </ClickAwayListener>
                              </Paper>
                          </Grow>
                      )}
                  </Popper>
                  <UpdateConfirmDialog selectedRecord={updateId} open={openUpdateDialogue} onClose={handleUpdateClose} onConfirm={() => handleUpdate(updateId)} />
              </fieldset>
          </form>
    </div>
  )
}