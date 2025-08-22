import Typography from '@mui/material/Typography';

export default function Page() {
  return (
    <>
      <div className='tab-group'>
        <Typography variant="h5">Services</Typography>
        <hr/>
        <a href="/simulation"><div className="service"><img src="/service_icon/simulation.svg" width='30px'/><Typography variant="body1">Simulation</Typography></div></a>
        <div className="service"><Typography variant="body1">Report</Typography></div>
        <div className="service"><img src="/service_icon/monitor.svg" width='30px'/><Typography variant="body1">Monitor</Typography></div>
        <div className="service"><Typography variant="body1">Marketplace</Typography></div>
      </div>
    </>
  )
}