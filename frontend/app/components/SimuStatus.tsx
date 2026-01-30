import { Chip, Link, Typography, Avatar, colors } from '@mui/material';
import { red, blue, lightGreen, grey, blueGrey } from '@mui/material/colors';
import AlarmIcon from '@mui/icons-material/Alarm';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

export default function SimuStatus(props) {
    let color: String = grey[200];
    let label: String = "Undetermined";
    let icon: any = <Avatar sx={{ bgcolor: grey[100], height: '28px', width: '28px' }}><AlarmIcon sx={{ color: grey[500] }} /></Avatar>;
    switch (props.status) {
        case "in_progress":
            color = blue[100];
            label = "In Progress";
            icon = <Avatar sx={{ bgcolor: grey[100], height: '28px', width: '28px' }}><AlarmIcon sx={{ color: grey[500] }} /></Avatar>;
            break;
        case "done":
            color = lightGreen[100];
            label = "Done";
            icon = <Avatar sx={{ bgcolor: lightGreen[100], height: '28px', width: '28px' }}><CheckCircleOutlineIcon sx={{ color: lightGreen[500] }} /></Avatar>;
            break;
        case "error":
            color = red[600];
            label = "Error";
            icon = <Avatar sx={{ bgcolor: red[100], height: '28px', width: '28px' }}><ErrorOutlineIcon sx={{ color: red[500] }} /></Avatar>;
            break;
    }
    return (<Chip sx={{ bgcolor: color }} icon={ icon } label={ label } />)
}