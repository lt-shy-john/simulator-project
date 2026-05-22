import { Typography, Alert, AlertTitle } from "@mui/material";
import { FieldErrors } from "react-hook-form";

type Props = {
    errors: FieldErrors;
};

export default function FormErrorBox({ errors }: Props) {
    const errorMessages = Object.values(errors)
        .map((error) => error?.message)
        .filter(Boolean);

    if (errorMessages.length === 0) return null;

    return (
        <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            <Typography>There are errors in the form: </Typography>
            {errorMessages.map((message, index) => (
                <Typography key={index} variant="body2">
                    • {message}
                </Typography>
            ))}
        </Alert>
    );
}