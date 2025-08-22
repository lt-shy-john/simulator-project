import { Card, CardActionArea, CardContent, CardActions, Box, Chip, Link, Typography } from '@mui/material';


export default function CardButton(props) {
    return (<Box>
        <Card sx={{ maxHeight: 345 }}>
            <CardActionArea>
                <CardContent><Typography variant="h5" component="div">{props.header}</Typography></CardContent>
                <CardContent><Typography variant="body2" sx={{ color: 'text.secondary' }}>{props.content}</Typography></CardContent>
                {props.wip == "true" && <Chip sx={{ margin: 2 }} color='warning' label="Out soon" />}
                {((props.wip == null || props.wip == undefined || props.wip !== "true") && props.link !== null) && <CardActions>
                    <Link sx={{ margin: 2 }} href={props.link}>Link</Link>
                </CardActions>}
            </CardActionArea>
        </Card>
        </Box>)
}