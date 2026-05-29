import { Chip, Link, Typography, Avatar, colors } from '@mui/material';
import { red, blue, lightGreen, green, grey, blueGrey } from '@mui/material/colors';
import AlarmIcon from '@mui/icons-material/Alarm';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import FiberNewOutlinedIcon from '@mui/icons-material/FiberNewOutlined';

export default function SimuStatus(props) {
    let color: String = grey[200];
    let label: String = "Undetermined";
    let icon: any = <Avatar sx={{ bgcolor: grey[100], height: '28px', width: '28px' }}><AlarmIcon sx={{ color: grey[500] }} /></Avatar>;
    let label_color: String = grey[800];
    const normalized = String(props.status ?? "").toLowerCase().replace(/\s+/g, "_");
    switch (normalized) {
        case "never_run":
        case "created":
            color = blueGrey[50];
            label = "Created";
            label_color = blueGrey[700];
            icon = <Avatar sx={{ bgcolor: blueGrey[50], height: '28px', width: '28px' }}><FiberNewOutlinedIcon sx={{ color: blueGrey[700] }} /></Avatar>;
            break;
        case "in_progress":
            color = blue[100];
            label = "In Progress";
            label_color = grey[500];
            icon = <Avatar sx={{ bgcolor: grey[100], height: '28px', width: '28px' }}><AlarmIcon sx={{ color: grey[500] }} /></Avatar>;
            break;
        case "done":
            color = lightGreen[100];
            label = "Done";
            label_color = green[800];
            icon = <Avatar sx={{ bgcolor: lightGreen[100], height: '28px', width: '28px' }}><CheckCircleOutlineIcon sx={{ color: green[800] }} /></Avatar>;
            break;
        case "error":
            color = red[100];
            label = "Error";
            label_color = red[900];
            icon = <Avatar sx={{ bgcolor: red[100], height: '28px', width: '28px' }}><ErrorOutlineIcon sx={{ color: red[500] }} /></Avatar>;
            break;
    }
    return (<Chip sx={{ bgcolor: color, "& .MuiChip-label": { color: label_color } }} icon={ icon } label={ label }/>)
}